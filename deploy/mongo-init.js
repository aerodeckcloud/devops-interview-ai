const appDbName = process.env.MONGO_INITDB_DATABASE || "ops_mentor_ai";
const appUser = process.env.MONGO_APP_USERNAME;
const appPassword = process.env.MONGO_APP_PASSWORD;

if (!appUser || !appPassword) {
  throw new Error("MONGO_APP_USERNAME and MONGO_APP_PASSWORD are required");
}

const appDb = db.getSiblingDB(appDbName);
appDb.createUser({
  user: appUser,
  pwd: appPassword,
  roles: [{ role: "readWrite", db: appDbName }],
});
