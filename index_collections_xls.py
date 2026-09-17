"""Export one JSON document per vereniging/bond, without connecting to Elasticsearch."""

import argparse
import os
from elasticsearch import Elasticsearch
from procrustus_indexer import build_indexer
from collections import Counter, defaultdict
from datetime import date, datetime
import json
from pathlib import Path
import re
import openpyxl

DATA_DIR = Path(__file__).parent / "data"
OUT_DIR = Path(__file__).parent / "json-data"
INDEX_NAME = "hi-sportdb"
CONFIG = "hi-sportdb-config.toml"
SHEETS = {
    "verenigingen": ("1_Verenigingen", "vereniging_id"),
    "relaties": ("2_Vereniging_relaties", "relatie_id"),
    "bronrecords": ("3_Bron_records", "bronrecord_id"),
    "plaatsen": ("4_Plaatsen", "plaats_id"),
    "gemeentes": ("5_Gemeentes_1984", "gemeente_1984_id"),
    "bonden": ("6_Bonden", "bond_id"),
    "lidmaatschappen": ("7_Bond_lidmaatschap", "lidmaatschap_id"),
    "bronnen": ("8_Bronnen", "bronvermelding_id"),
    "notities": ("9_Curator_notities", "notitie_id"),
}


def create_es_client() -> Elasticsearch:
    es_host = os.environ.get("ES_HOST", "localhost")
    es_port = os.environ.get("ES_PORT", "9200")
    es_scheme = os.environ.get("ES_SCHEME", "http")
    es_username = os.environ.get("ES_USERNAME", "")
    es_password = os.environ.get("ES_PASSWORD", "")
    es_verify_certs = (es_scheme != "https")
    es_ssl_show_warn = (es_scheme != "https")
    return Elasticsearch(hosts=[f"{es_scheme}://{es_host}:{es_port}"],
                         basic_auth=(es_username, es_password),
                         verify_certs=es_verify_certs,
                         ssl_show_warn=es_ssl_show_warn)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "workbook",
        nargs="?",
        type=Path,
        default=Path(DATA_DIR) / "Dataset_uit_csv.xlsx"
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=OUT_DIR,
        help="New or empty export directory (default: json-data)")
    parser.add_argument(
        "-k",
        "--skip-import",
        type=bool,
        default=False,
        help=f"Skip importing XML files into ElasticSearch (default: {False}).")
    return parser.parse_args()

def import_into_es(
    index_name: str, cfg: str, es_client: Elasticsearch, input_dir: Path
) -> None:
    inputs = [str(p) for p in sorted(input_dir.rglob("*.json"))]
    if not inputs:
        print(f"Skipping ES import: no input files found under {input_dir}")
        return

    if not Path(cfg).exists():
        print(f"Skipping ES import: config not found: {cfg}")
        return

    indexer = build_indexer(cfg, index_name, es_client)
    indexer.create_mapping(overwrite=True)
    indexer.import_files(inputs)
    print(f"Imported {len(inputs)} files into Elasticsearch index '{index_name}'")


def text(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def split_values(value):
    return [part.strip() for part in (text(value) or "").split("|") if part.strip()]


def normalized(row):
    """Normalize identifiers without altering the separately retained raw values."""
    return {key: text(value) if key.endswith("_id") or key in
            {"cbs_code", "a_code", "paginas", "jaar_deel_uitgave", "ppn"}
            else value for key, value in row.items()}


def historical_date(value, meaning, sources, field, issues):
    raw = text(value)
    result = dict(waarde=raw, precisie=None, jaar=None, maand=None, dag=None,
                  betekenis=meaning)
    components = None
    if raw is not None:
        try:
            if not re.fullmatch(r"\d{4}(?:-\d{2}){0,2}", raw):
                raise ValueError("date format")
            parts = [int(part) for part in raw.split("-")]
            date(parts[0], parts[1] if len(parts) > 1 else 1,
                 parts[2] if len(parts) > 2 else 1)
            components = tuple(parts + [None] * (3 - len(parts)))
        except ValueError:
            issues.append(f"{field}_ongeldig")
    conflict = False
    for source in sources:
        values = tuple(source.get(f"{field}_bron{unit}") for unit in ("jaar", "maand", "dag"))
        if values != (None, None, None) and values != components:
            conflict = True
    if conflict:
        issues.append(f"{field}_broncomponenten_conflict")
    if components and not conflict:
        result.update(zip(("jaar", "maand", "dag"), components))
        result["precisie"] = ("jaar", "maand", "dag")[sum(v is not None for v in components) - 1]
    return result


def owner(row, membership=False):
    club = text(row.get("vereniging_id"))
    bond = text(row.get("lid_bond_id" if membership else "bond_id"))
    if bool(club) == bool(bond):
        return None
    kind, identifier = ("vereniging", club) if club else ("bond", bond)
    if membership and row.get("lidtype") != kind:
        return None
    return f"{kind}:{identifier}"


def read_tables(path):
    tables = {}
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        for name, (sheet, primary_key) in SHEETS.items():
            if sheet not in workbook.sheetnames:
                raise ValueError(f"Missing worksheet: {sheet}")
            iterator = workbook[sheet].iter_rows(values_only=True)
            headers = next(iterator)
            if primary_key not in headers or None in headers or len(set(headers)) != len(headers):
                raise ValueError(f"Invalid headers in {sheet}")
            rows = []
            seen = set()
            for number, values in enumerate(iterator, 2):
                if all(value is None for value in values):
                    continue
                row = dict(zip(headers, values))
                identifier = text(row[primary_key])
                if not identifier or identifier in seen:
                    raise ValueError(f"Missing/duplicate {primary_key} at {sheet}!{number}")
                seen.add(identifier)
                rows.append((number, row))
            tables[name] = rows
    finally:
        workbook.close()
    return tables


class Converter:
    def __init__(self, path):
        self.path = Path(path)
        self.tables = read_tables(path)
        self.report = {
            "bestand": self.path.name,
            "rijen_per_sheet": {SHEETS[k][0]: len(v) for k, v in self.tables.items()},
            "documenten": {}, "meldingen": [], "quarantaine": [],
        }
        self.entities = {}
        for kind, table in (("vereniging", "verenigingen"), ("bond", "bonden")):
            for number, row in self.tables[table]:
                identifier = text(row[f"{kind}_id"])
                if not re.fullmatch(r"[0-9]+", identifier):
                    raise ValueError(f"Unsafe/non-numeric entity ID: {identifier!r}")
                self.entities[f"{kind}:{identifier}"] = (kind, table, number, row)
        self.places = {text(r["plaats_id"]): r for _, r in self.tables["plaatsen"]}
        self.municipalities = {text(r["gemeente_1984_id"]): r for _, r in self.tables["gemeentes"]}
        self.groups = {key: defaultdict(list) for key in
                       ("bronrecords", "lidmaatschappen", "relaties", "bronnen", "notities")}
        self.place_notes = defaultdict(list)
        self.municipality_notes = defaultdict(list)
        self.source_owners = {}
        self._group_rows()

    def quarantine(self, table, number, row, reason):
        self.report["quarantaine"].append({"sheet": SHEETS[table][0], "rij": number,
                                           "reden": reason, "ruwe_waarden": row})

    def _group_rows(self):
        for table in ("bronrecords", "lidmaatschappen", "relaties", "bronnen"):
            for number, row in self.tables[table]:
                entity_id = owner(row, membership=table == "lidmaatschappen")
                if entity_id not in self.entities:
                    self.quarantine(table, number, row, "ongeldige_of_onbekende_eigenaar")
                    continue
                if table == "bronrecords":
                    if row.get("recordsoort") != entity_id.split(":")[0]:
                        self.quarantine(table, number, row, "recordsoort_conflict")
                        continue
                    self.source_owners[text(row["bronrecord_id"])] = entity_id
                self.groups[table][entity_id].append(row)
        for number, row in self.tables["notities"]:
            if row.get("objectsoort") == "plaatsen":
                identifier = text(row.get("plaats_id"))
                if identifier in self.places:
                    self.place_notes[identifier].append(normalized(row))
                    continue
            elif row.get("gemeente_1984_id") is not None:
                identifier = text(row["gemeente_1984_id"])
                if identifier in self.municipalities:
                    self.municipality_notes[identifier].append(normalized(row))
                    continue
            else:
                entity_id = owner(row)
                if entity_id in self.entities:
                    self.groups["notities"][entity_id].append(normalized(row))
                    continue
            self.quarantine("notities", number, row, "onbekend_notitiedoel")

    def location(self, canonical, issues):
        place_id = text(canonical.get("plaats_id"))
        municipality_id = text(canonical.get("gemeente_1984_id"))
        place = self.places.get(place_id)
        municipality = self.municipalities.get(municipality_id)
        if not place:
            issues.append("plaats_ontbreekt" if not place_id else "plaats_id_onbekend")
        if not municipality:
            issues.append("gemeente_1984_ontbreekt" if not municipality_id else "gemeente_1984_id_onbekend")
        place_doc = None
        if place:
            place_doc = normalized(place)
            place_doc["id"] = place_doc.pop("plaats_id")
            place_doc["namen_in_bron"] = split_values(place["namen_in_bron"])
            place_doc["coordinaten_bron"] = {key: text(place_doc.pop(key)) for key in
                                               ("breedtegraad", "lengtegraad")}
            place_doc["geo"] = None
            place_doc["curator_notities"] = self.place_notes[place_id]
            place_doc["ruwe_waarden"] = place
            issues.append("plaatscoordinaten_nog_niet_gevalideerd")
        municipality_doc = None
        if municipality:
            municipality_doc = normalized(municipality)
            municipality_doc["id"] = municipality_doc.pop("gemeente_1984_id")
            municipality_doc["curator_notities"] = self.municipality_notes[municipality_id]
            municipality_doc["ruwe_waarden"] = municipality
        return {
            "plaats": place_doc, "plaats_bron": canonical.get("plaats"),
            "gemeente_1984": municipality_doc,
            "gemeente_1984_bron": canonical.get("gemeente_1984", canonical.get("gemeente_1984_bron")),
            "provincie": canonical.get("provincie"),
        }

    def document(self, entity_id):
        kind, table, number, entity = self.entities[entity_id]
        sources = self.groups["bronrecords"][entity_id]
        issues = []
        if len(sources) != entity.get("aantal_bronrecords"):
            issues.append("aantal_bronrecords_conflict")
        # Do not choose arbitrarily when a future workbook supplies several sources.
        canonical = entity if kind == "vereniging" else sources[0] if len(sources) == 1 else {}
        if kind == "bond" and len(sources) != 1:
            issues.append("bond_zonder_bronrecord" if not sources else "bond_meerdere_bronrecords")
        memberships = []
        for row in self.groups["lidmaatschappen"][entity_id]:
            target = text(row["bond_id"])
            target_id = f"bond:{target}" if target else None
            if target_id and target_id not in self.entities:
                issues.append(f"lidmaatschap:{row['lidmaatschap_id']}:bond_id_onbekend")
            begin, end = row["beginjaar"], row["eindjaar"]
            valid_years = all(value is None or
                              (type(value) is int and 1000 <= value <= 9999)
                              for value in (begin, end))
            if not valid_years:
                issues.append(f"lidmaatschap:{row['lidmaatschap_id']}:jaar_verdacht")
            if type(begin) is int and type(end) is int and begin > end:
                issues.append(f"lidmaatschap:{row['lidmaatschap_id']}:omgekeerde_periode")
            memberships.append({
                "id": text(row["lidmaatschap_id"]), "bronrecord_id": text(row["bronrecord_id"]),
                "bond": {"id": target_id, "bond_id": target, "naam": row["bond_naam"]},
                "niveau": row["niveau"], "bondsvermelding": row["bondsvermelding"],
                "beginjaar": begin if type(begin) is int else None,
                "eindjaar": end if type(end) is int else None,
                "koppelstatus": row["koppelstatus"], "ruwe_waarden": row,
            })
        relations = []
        for row in self.groups["relaties"][entity_id]:
            if not row["relatietype"] or not row["genoemde_organisatie"]:
                issues.append(f"relatie:{row['relatie_id']}:onvolledig")
            relations.append({
                "id": text(row["relatie_id"]), "bronrecord_id": text(row["bronrecord_id"]),
                "relatietype": row["relatietype"],
                "doel": {"id": None, "naam_bron": row["genoemde_organisatie"]},
                "koppelstatus": "niet_gekoppeld", "ruwe_waarden": row,
            })
        source_docs = []
        for row in sources:
            source_docs.append({"id": text(row["bronrecord_id"]), **{
                key: row.get(key) for key in ("recordstatus", "broncollectie", "broncategorie",
                    "bronbestand", "naam_opmerking", "verantwoording", "opmerkingen", "aantekeningen")},
                "ruwe_waarden": row})
            if not row.get("bronbestand"):
                issues.append(f"bronrecord:{row['bronrecord_id']}:bronbestand_ontbreekt")
        for group in ("lidmaatschappen", "relaties", "bronnen"):
            for row in self.groups[group][entity_id]:
                if self.source_owners.get(text(row["bronrecord_id"])) != entity_id:
                    issues.append(f"{group}:bronrecord_eigenaar_conflict:{row['bronrecord_id']}")
        citations = [{**normalized(row), "ruwe_waarden": row}
                     for row in self.groups["bronnen"][entity_id]]
        doc = {
            "schema_versie": 1, "id": entity_id, "type": kind,
            f"{kind}_id": text(entity[f"{kind}_id"]), "naam": entity["naam"],
            "alternatieve_namen": split_values(canonical.get("alternatieve_namen")),
            "sport": split_values(entity.get("sport")),
            "levensbeschouwing": canonical.get("levensbeschouwing"),
            "werkingsgebied": split_values(canonical.get("werkingsgebied")),
            "speeldag": canonical.get("speeldag"), "locatie": self.location(canonical, issues),
            "wikidata": {"id": text(entity.get("wikidata_id")),
                         "url": entity.get("wikidata_url"), "label": entity.get("wikidata_label")},
            "lidmaatschappen": memberships, "relaties": relations, "bronnen": citations,
            "bronrecords": source_docs, "curator_notities": self.groups["notities"][entity_id],
            "herkomst": {"bestand": self.path.name, "entiteit_sheet": SHEETS[table][0],
                         "entiteit_rij": number, "aantal_bronrecords": entity.get("aantal_bronrecords"),
                         "aangevulde_velden_bronrecord_id": text(sources[0]["bronrecord_id"])
                         if kind == "bond" and len(sources) == 1 else None,
                         "ruwe_waarden": entity},
        }
        for field in ("begindatum", "einddatum"):
            doc[field] = historical_date(canonical.get(field), canonical.get(f"{field}_betekenis"),
                                         sources, field, issues)
        if kind == "vereniging":
            doc["identificatie"] = {"status": entity.get("identificatiestatus"),
                                   "toelichting": entity.get("identificatie_toelichting")}
        else:
            doc["bond"] = {key: entity.get(key) for key in ("niveau", "landelijke_context", "notities")}
            doc["bond"]["namen_in_bron"] = split_values(entity.get("namen_in_bron"))
        doc["datakwaliteit"] = {"meldingen": sorted(set(issues))}
        return doc

    def export(self, output):
        output = Path(output)
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise ValueError(f"Output must be a new or empty directory: {output}")
        output.mkdir(parents=True, exist_ok=True)
        counts = Counter()
        totals = Counter()
        for entity_id in self.entities:
            doc = self.document(entity_id)
            directory = output / "organisaties" / doc["type"]
            directory.mkdir(parents=True, exist_ok=True)
            write_json(directory / f"{doc[doc['type'] + '_id']}.json", doc)
            counts[doc["type"]] += 1
            for group in ("bronrecords", "lidmaatschappen", "relaties", "bronnen"):
                totals[group] += len(doc[group])
            if doc["datakwaliteit"]["meldingen"]:
                self.report["meldingen"].append({"id": entity_id, **doc["datakwaliteit"]})
        self.report["documenten"] = dict(counts)
        self.report["gekoppelde_rijen"] = dict(totals)
        self.report["gekoppelde_notities"] = (sum(len(rows) for rows in self.place_notes.values()) + sum(
            len(rows) for rows in self.municipality_notes.values()) + sum(
            len(rows) for rows in self.groups["notities"].values()))
        write_json(output / "conversion_report.json", self.report)
        return self.report


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               default=text, allow_nan=False) + "\n", encoding="utf-8")


def main():
    args = parse_args()

    print(f"Reading {args.workbook} ...", flush=True)
    report = Converter(args.workbook).export(args.output_dir)

    print(f"Wrote {sum(report['documenten'].values()):,} documents to {args.output_dir / 'organisaties'}")
    print(f"Quarantined rows: {len(report['quarantaine'])}; report: {args.output_dir / 'conversierapport.json'}")

    if not args.skip_import:
        import_into_es(INDEX_NAME, CONFIG, create_es_client(), args.output_dir)


if __name__ == "__main__":
    main()
