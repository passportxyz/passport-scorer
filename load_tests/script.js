import http from "k6/http";
import { sleep } from "k6";
import exec from "k6/execution";
import { randomSeed } from "k6";
import { check } from "k6";

randomSeed(234123521532);
function getRandomInt(max) {
  const ret = Math.floor(Math.random() * max);
  // console.log("getRandomInt ", ret);
  return ret;
}

// import HDWallet from "https://cdn.jsdelivr.net/npm/ethereum-hdwallet@latest/ethereum-hdwallet.js";

// console.log("HDWallet", HDWallet)
// const mnemonic = 'tag volcano eight thank tide danger coast health above argue embrace heavy'
// const hdwallet = HDWallet.fromMnemonic(mnemonic)
// console.log(`0x${hdwallet.derive(`m/44'/60'/0'/0/0`).getAddress().toString('hex')}`) // 0xc49926c4124cee1cba0ea94ea31a6c12318df947

export const options = {
  ext: {
    loadimpact: {
      projectID: 3643521,
      // Test runs with the same name groups test runs together
      name: "Test create passports",
      distribution: {
        US: { loadZone: "amazon:us:ashburn", percent: 50 },
        Ireland: { loadZone: "amazon:ie:dublin", percent: 50 },
        // Sweden: { loadZone: 'amazon:se:stockholm', percent: 34 },
      },
    },
  },

  vus: 1,
  duration: "15s",
  // duration: "60s",
  // duration: "5m",
};

// console.log("This is init code: ", exec.vu.idInInstance);
// console.log("This is init code: ", exec.vu.idInTest);

const scorerId = 24;
const apiKey = "rSlchz0V.HFjzHxwjoInlqk3tY3XyRGOCKMUUmQcC";
const numAccounts = 1000;

export function setup() {}

export function teardown(data) {}

const addresses = JSON.parse(
  open(`./test_data/generated_accounts_${numAccounts}.json`)
);

const userTokens = JSON.parse(
  open("./generate_test_auth_tokens/user-tokens.json")
);

// const vcsForAddress = [];
const allVcs = [];

for (let i = 0; i < 100; i++) {
  const address = addresses[i];
  const vcs = JSON.parse(open(`./test_data/vcs/${address}_vcs.json`));
  // vcsForAddress.push(vcs);
  for (let j = 0; j < vcs.length; j++) {
    allVcs.push(vcs[j]);
  }
}

// create k6 setup and teardown
export default function () {
  // const idx = exec.vu.idInInstance - 1;
  // console.log("This is vu info: ", exec.vu.idInInstance);

  const addressIdx = getRandomInt(numAccounts);
  const address = addresses[addressIdx];
  const token = userTokens[address];
  // const vcs = vcsForAddress[addressIdx];
  // const vcs = [];
  // console.log("address", address);

  const options = {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  };

  // We simulate 4 batches of changes to a users passport
  for (let i = 0; i < 4; i++) {
    const bodyDelete = [];
    const body = [];
    for (let j = 0; j < 10; j++) {
      const vcIdx = getRandomInt(allVcs.length);
      const stamp = allVcs[vcIdx];
      const provider = stamp.credentialSubject.provider;
      // Make sure we do not have duplicate providers in our request
      if (bodyDelete.findIndex((e) => e.provider === provider) === -1) {
        body.push({
          provider,
          stamp,
        });
        bodyDelete.push({
          provider,
        });
      }
    }

    //////////////////////////////////////////////////////////////////////////////////////
    // User claims some stamps. In the Passport app, the user would normally claim stamps
    // in batches (for example, claim Twitter stamp - batch 1, some EVM stamps - batch 2, Gitcoin stamps - batch 3, etc.)
    //
    // For each batch we will do the following:
    // 1. delete existing stamps
    // 2. post new stamps
    //////////////////////////////////////////////////////////////////////////////////////

    // Delete any existing providers
    const resDel = http.del(
      "https://api.staging.scorer.gitcoin.co/ceramic-cache/stamps/bulk",
      JSON.stringify(bodyDelete),
      options
    );
    // console.log(
    //   "This is delete body: ",
    //   JSON.stringify(bodyDelete, undefined, 2)
    // );
    // console.log(
    //   "This is delete response: ",
    //   JSON.stringify(resDel, undefined, 2)
    // );

    // Post new providers
    const res = http.post(
      "https://api.staging.scorer.gitcoin.co/ceramic-cache/stamps/bulk",
      JSON.stringify(body),
      options
    );

    check(res, {
      "is status 201": (r) => r.status === 201,
    });

    if (res.status !== 201) {
      console.log("Saving stamps failed: ", JSON.stringify(res, undefined, 2));
    }
  }

  //////////////////////////////////////////////////////////////////////////////////////
  // Now the user scores his passport.
  //////////////////////////////////////////////////////////////////////////////////////

  const scoringOptions = {
    headers: {
      "X-API-Key": apiKey,
      "Content-Type": "application/json",
    },
  };

  const res = http.post(
    "https://api.staging.scorer.gitcoin.co/registry/submit-passport",
    JSON.stringify({
      address: address,
      community: scorerId,
    }),
    scoringOptions
  );

  check(res, {
    "is status 200": (r) => r.status === 200,
  });

  if (res.status !== 200) {
    console.log(
      "Submitting passport for scoring failed: ",
      JSON.stringify(res, undefined, 2)
    );
  }

  let isScorePending = true;
  const maxRequests = 10;
  let numRequests = 0;
  let sleepTime = 1;
  while (isScorePending && numRequests < maxRequests) {
    numRequests += 1;

    const res = http.get(
      `https://api.staging.scorer.gitcoin.co/registry/score/${scorerId}/${address}`,
      scoringOptions
    );

    check(res, {
      "is status 200": (r) => r.status === 200,
    });

    const data = res.json();

    console.log("data", data);

    if (data["status"] !== "PROCESSING") {
      isScorePending = false;
    } else {
      sleep(sleepTime);
      sleepTime *= 2;
    }
  }
}
