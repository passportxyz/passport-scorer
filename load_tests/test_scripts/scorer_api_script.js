import http from "k6/http";
import exec from "k6/execution";
import { randomSeed } from "k6";
import { check } from "k6";
import { SharedArray } from "k6/data";

randomSeed(234123521532);
function getRandomInt(max) {
  const ret = Math.floor(Math.random() * max);
  return ret;
}

export const options = {
  ext: {
    loadimpact: {
      projectID: 3643521,
      // Test runs with the same name groups test runs together
      name: "Test create passports",
      distribution: {
        US: { loadZone: "amazon:us:ashburn", percent: 50 },
        Ireland: { loadZone: "amazon:ie:dublin", percent: 50 },
      },
    },
  },
};

// const scorerId = __ENV.SCORER_ID;
// const apiKey = __ENV.SCORER_API_KEY;
const numAccounts = Number.parseInt(__ENV.NUM_ACCOUNTS);

export function setup() { }

export function teardown(data) { }

const addresses = JSON.parse(
  open(`../test_data/generated_accounts_${numAccounts}.json`)
);

const userTokens = JSON.parse(
  open("../generate_test_auth_tokens/user-tokens.json")
);

const userVcs = new SharedArray("userVcs", function() {
  const userVcs = [];

  for (let i = 0; i < numAccounts; i++) {
    const address = addresses[i];
    const vcs = JSON.parse(open(`../test_data/vcs/${address}_vcs.json`));
    userVcs.push(vcs);
  }

  return userVcs;
});

// create k6 setup and teardown
export default function() {
  // To avoid deadlock, # VUs should be <= # accounts
  const addressIdx = (exec.vu.idInTest - 1) % numAccounts;

  const address = addresses[addressIdx];
  const vcs = userVcs[addressIdx];
  const token = userTokens[address];

  const requestOptions = {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    timeout: '90s',
  };

  ///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  // Make fetch request, eventhough the response is not used in the auth request, it is still being made
  ///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  const nonceResponse = http.get(
    "https://api.staging.scorer.gitcoin.co/account/nonce"
  );

  check(nonceResponse, {
    "Nonce status 200": (r) => r.status === 200,
  });

  if (nonceResponse.status !== 200) {
    console.log(
      "Nonce Request failed: ",
      JSON.stringify(nonceResponse, undefined, 2)
    );
  }

  ///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  // Although this is not the response we are expect, it seems useful to still make the request
  ///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  // const authRequest = http.post(
  //   "https://api.staging.scorer.gitcoin.co/ceramic-cache/authenticate",
  //   JSON.stringify(verifierPayload),
  //   scoringOptions
  // );

  // check(authRequest, {
  //   "Auth status 400": (r) => r.status === 400,
  // });

  // if (authRequest.status !== 400) {
  //   console.log(
  //     "Auth Request failed: ",
  //     JSON.stringify(authRequest, undefined, 2)
  //   );
  // }

  ////////////////////////////////////////////////////////////////////////////////////////////////////
  // Fetch score weights
  ////////////////////////////////////////////////////////////////////////////////////////////////////

  const weightRequest = http.get(
    "https://api.staging.scorer.gitcoin.co/ceramic-cache/weights",
    options
  );

  check(weightRequest, {
    "Weight fetch request is status 200": (r) => r.status === 200,
  });

  if (weightRequest.status !== 200) {
    console.log("Weight request failed: ", JSON.stringify(weightRequest, undefined, 2));
  }


  ////////////////////////////////////////////////////////////////////////////////////////////////////
  // Fetch stamps
  ////////////////////////////////////////////////////////////////////////////////////////////////////

  const stampRequest = http.get(
    "https://api.staging.scorer.gitcoin.co/ceramic-cache/stamp?address=" + address,
    options
  );

  check(stampRequest, {
    "stampRequest fetch request is status 200": (r) => r.status === 200,
  });

  if (stampRequest.status !== 200) {
    console.log("stampRequest failed: ", JSON.stringify(stampRequest, undefined, 2));
  }

  ////////////////////////////////////////////////////////////////////////////////////////////////////
  // Fetch banners
  ////////////////////////////////////////////////////////////////////////////////////////////////////

  const bannerRequest = http.get(
    "https://api.staging.scorer.gitcoin.co/passport-admin/banners",
    requestOptions
  );

  check(bannerRequest, {
    "Banner fetch request is status 200": (r) => r.status === 200,
  });

  if (bannerRequest.status !== 200) {
    console.log("Banner request failed: ", JSON.stringify(bannerRequest, undefined, 2));
  }

  // We simulate 4 batches of changes to a users passport
  for (let i = 0; i < 4; i++) {
    const body = [];
    for (let j = 0; j < 6; j++) {
      const stamp = vcs[getRandomInt(vcs.length)];
      const provider = stamp.credentialSubject.provider;

      // Make sure we do not have duplicate providers in our request
      if (body.find((e) => e.provider === provider)) continue;

      if (Math.random() < 0.5) {
        // To be deleted
        body.push({
          provider,
        });
      } else {
        // To be added/updated
        body.push({
          provider,
          stamp,
        });
      }
    }

    //////////////////////////////////////////////////////////////////////////////////////
    // User claims some stamps. In the Passport app, the user would normally claim stamps
    // in batches (for example, claim Twitter stamp - batch 1, some EVM stamps - batch 2, Gitcoin stamps - batch 3, etc.)
    //
    // For each batch we will make a patch request to create/update/delete stamps.
    //////////////////////////////////////////////////////////////////////////////////////

    const res = http.patch(
      "https://api.staging.scorer.gitcoin.co/ceramic-cache/stamps/bulk",
      JSON.stringify(body),
      requestOptions
    );

    check(res, {
      "Saving Stamps request is status 200": (r) => r.status === 200,
    });

    if (res.status !== 200) {
      console.log("Saving stamps failed: ", JSON.stringify(res, undefined, 2));
    }

    ////////////////////////////////////////////////////////////////////////////////////////////////////
    // After user submits their new stamps we fetch their score
    ////////////////////////////////////////////////////////////////////////////////////////////////////

    const scoreRes = http.get(
      "https://api.staging.scorer.gitcoin.co/ceramic-cache/score/" + address,
      requestOptions
    );

    check(scoreRes, {
      "Score fetch request is status 200": (r) => r.status === 200,
    });

    if (scoreRes.status !== 200) {
      console.log("Fetching score failed: ", JSON.stringify(scoreRes, undefined, 2));
    }
  }
}
