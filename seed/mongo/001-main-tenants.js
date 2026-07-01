const TENANT_NAME = "tenant-sport";
const TENANT_DOMAIN_LOCAL = "localhost";
const TENANT_DOMAIN_SD = "sport.sd.di.huc.knaw.nl";

const mainDb = db.getSiblingDB("main");

mainDb.tenants.createIndex({ domain: 1 }, { unique: true });

mainDb.tenants.updateOne(
    { domain: TENANT_DOMAIN_LOCAL },
    { $set: { name: TENANT_NAME, domain: TENANT_DOMAIN_LOCAL } },
    { upsert: true }
);

mainDb.tenants.updateOne(
    { domain: TENANT_DOMAIN_SD },
    { $set: { name: TENANT_NAME, domain: `${TENANT_DOMAIN_SD}` } },
    { upsert: true }
);