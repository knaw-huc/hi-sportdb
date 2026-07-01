const TENANT_DB = "tenant-sport";
const DATASET_NAME = "sport";

const tenantDb = db.getSiblingDB(TENANT_DB);

tenantDb.detail_properties.deleteMany({ dataset_name: DATASET_NAME });
tenantDb.detail_properties.insertMany([
    { dataset_name: DATASET_NAME, name: "vereniging", type: "screen", path: "$", order: 1, config: {
        "id": "vereniging-detail",
        "screenType": "normal",
        "globals": {},
        "form": {
            "rows": [
              {
                "displayType": "group",
                "groupId": "vereniging",
                "elements": [
                  {
                    "value": "$data#$.naam",
                    "type": "label"
                  },
                  {
                    "value": "$data#$.plaats",
                    "type": "label"
                  },
                  {
                    "value": "$data#$.provincie",
                    "type": "label"
                  },
                  {
                    "value": "$data#$.doelstelling",
                    "type": "markdown"
                  },
                  {
                    "value": "$data#$.levensbeschouwing",
                    "type": "label"
                  },
                  {
                    "value": "$data#$.beginDatumJaar",
                    "type": "label"
                  },
                  {
                    "value": "$data#$.werkingsGebied",
                    "type": "label"
                  },
                  {
                    "value": "$data#$.landelijkeBond",
                    "type": "list"
                  },
                  {
                    "value": "$data#$.regionaleBond",
                    "type": "list"
                  },
                  {
                    "value": "$data#$.speeldag",
                    "type": "label"
                  },
                  {
                    "value": "$data#$.koninklijkBesluit",
                    "type": "label"
                  },
                  {
                    "value": "$data#$.verantwoordingGegevens",
                    "type": "markdown"
                  },
                  {
                    "value": "$data#$.opmerkingen",
                    "type": "markdown"
                  }
                ]
              }
            ]
          }
        }
    }
]);