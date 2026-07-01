const DATA_TYPE_ELASTIC = "elasticsearch";
const TENANT_DB = "tenant-sport";
const DATASET_NAME = "sport";
const ES_INDEX = "hi-sportdb";
const DATA_TYPE = DATA_TYPE_ELASTIC;

const tenantDb = db.getSiblingDB(TENANT_DB);

const dataConfiguration = { id_property: "", base_url: "" };

tenantDb.datasets.updateOne(
    {
        tenant_name: TENANT_DB,
        name: DATASET_NAME
    },
    {
        $set: {
            tenant_name: TENANT_DB,
            name: DATASET_NAME,
            es_index: `${ES_INDEX}`,
            data_type: DATA_TYPE,
            data_configuration: {
                ...dataConfiguration,
                home_url: `/${DATASET_NAME}/search`
            },
            detail_id: "_id",
            metadata: { }
        }
    },
    { upsert: true }
);

