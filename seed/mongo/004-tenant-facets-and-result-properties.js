const TENANT_DB = "tenant-sport";
const DATASET_NAME = "sport";

const tenantDb = db.getSiblingDB(TENANT_DB);

// ---------- FACETS ----------
tenantDb.facets.deleteMany({ dataset_name: DATASET_NAME });
 tenantDb.facets.insertMany([
     { dataset_name: DATASET_NAME, name: "Sport", property: "sport", type: "text", order: 0 },
     { dataset_name: DATASET_NAME, name: "Naam", property: "naam", type: "text", order: 1 },
     { dataset_name: DATASET_NAME, name: "Type", property: "type", type: "text", order: 2 },
     { dataset_name: DATASET_NAME, name: "Plaats", property: "plaats", type: "text", order: 3 },
     { dataset_name: DATASET_NAME, name: "Provincie", property: "provincie", type: "text", order: 4 },
     { dataset_name: DATASET_NAME, name: "Beginjaar", property: "beginDatumJaar", type: "number", order: 5 },
     { dataset_name: DATASET_NAME, name: "Status beginjaar", property: "beginDatumSoort", type: "text", order: 6 },
     { dataset_name: DATASET_NAME, name: "Eindjaar", property: "eindDatumJaar", type: "number", order: 7 },
     { dataset_name: DATASET_NAME, name: "Status eindjaar", property: "eindDatumSoort", type: "text", order: 8 },
     { dataset_name: DATASET_NAME, name: "Levensbeschouwing", property: "levensbeschouwing", type: "text", order: 9 }
]);

// ---------- RESULT PROPERTIES ----------
tenantDb.result_properties.createIndex({ dataset_name: 1, order: 1 }, { unique: true });
tenantDb.result_properties.deleteMany({ dataset_name: DATASET_NAME });
tenantDb.result_properties.insertMany([
    { dataset_name: DATASET_NAME, name: "id", path: "$.id", type: 'text', order: 0 },
    { dataset_name: DATASET_NAME, name: "title", path: "$.naam", type: 'text', order: 1 },
    { dataset_name: DATASET_NAME, name: "place", path: "$.plaats", type: 'text', order: 2 },
    { dataset_name: DATASET_NAME, name: "province", path: "$.provincie", type: 'text', order: 3 },
    { dataset_name: DATASET_NAME, name: "sport", path: "$.sport", type: 'text', order: 4 },
    { dataset_name: DATASET_NAME, name: "startDateYear", path: "$.beginDatumJaar", type: 'text', order: 5 },
    { dataset_name: DATASET_NAME, name: "philosophy", path: "$.levensbeschouwing", type: 'text', order: 6 },
]);