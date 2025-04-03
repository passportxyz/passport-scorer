require("dotenv").config();

module.exports = {
  testTimeout: parseInt(process.env.TEST_TIMEOUT || "60000"), // 60 s timeout
  preset: "ts-jest",
  testEnvironment: "node",
  roots: ["<rootDir>/src"],
  testMatch: ["**/*.test.ts"],
  reporters: ["default", "<rootDir>/jest/DBLoggerReporter.js"],
  setupFiles: ["dotenv/config"],
  setupFilesAfterEnv: ["<rootDir>/jest/setupAfterEnv.js"],
  moduleFileExtensions: ["ts", "js", "json", "node"],
  moduleNameMapper: {
    "^uint8arrays(.*)$": "<rootDir>/node_modules/uint8arrays/dist/src$1",
    "^multiformats(.*)$": "<rootDir>/node_modules/multiformats/dist/src$1",
    "^@ipld/dag-cbor(.*)$": "<rootDir>/node_modules/@ipld/dag-cbor/dist/index.min.js",
  },
  extensionsToTreatAsEsm: [".ts"],
  transformIgnorePatterns: [
    "(^|/)node_modules/(?!(@didtools|codeco|uint8arrays|multiformats|did-session|key-did-provider-ed25519|rpc-utils|key-did-resolver|dids|dag-jose-utils)/)",
  ],
  transform: {
    "(^|/)node_modules/(@didtools|codeco|uint8arrays|multiformats|did-session|key-did-provider-ed25519|rpc-utils|key-did-resolver|dids|dag-jose-utils)/.*.js$":
      "babel-jest",
    "(^|/)src/.*.ts$": "ts-jest",
  },
};
