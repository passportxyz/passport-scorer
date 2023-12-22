import http from "k6/http";
import exec from "k6/execution";
import { check } from "k6";
import { SharedArray } from "k6/data";

export const options = {
  ext: {
    loadimpact: {
      projectID: 3643521,
      // Test runs with the same name groups test runs together
      name: "Test issue credentials",
      distribution: {
        US: { loadZone: "amazon:us:ashburn", percent: 50 },
        Ireland: { loadZone: "amazon:ie:dublin", percent: 50 },
      },
    },
  },
};

export function setup() {
  const userAccounts = [];

  for (let i = 0; i < numAccounts; i++) {
    let getAddressResponse;
    while (
      getAddressResponse === undefined ||
      getAddressResponse.status !== 200
    ) {
      getAddressResponse = http.get(signerUrl + "generate");
    }
    const { address, privateKey } = JSON.parse(getAddressResponse.body);
    userAccounts.push({ address, privateKey });
  }

  return { userAccounts: userAccounts };
}

export function teardown(data) {}

const iamUrl = "https://iam.staging.passport.gitcoin.co/api/v0.0.0/";
const signerUrl = "http://localhost:8123/";
const numAccounts = 1000;

// create k6 setup and teardown
export default async function (data) {
  const { userAccounts } = data;
  const accountIndex = (exec.vu.idInTest - 1) % userAccounts.length;
  const { address, privateKey } = userAccounts[accountIndex];

  const options = {
    headers: {
      "Content-Type": "application/json",
    },
  };

  const trackedRequestOptions = Object.assign({}, options, {
    tags: { tracked: "true" },
  });

  // We simulate 4 batches of claiming stamps
  let credentials;
  for (let i = 0; i < 4; i++) {
    const challengeResponse = http.post(
      iamUrl + "challenge",
      JSON.stringify({
        payload: {
          address,
          type: "Simple",
          signatureType: "Ed25519",
        },
      }),
      trackedRequestOptions
    );

    check(challengeResponse, {
      "is status 200": (r) => r.status === 200,
    });

    if (challengeResponse.status !== 200) {
      console.log(
        "Fetching challenge failed: ",
        JSON.stringify(challengeResponse, undefined, 2)
      );
      return;
    }

    const challenge = JSON.parse(challengeResponse.body).credential;

    // These requests fail like 60% of the time b/c of IO resource
    // issues on localhost, so just retry until we get a 200
    let signatureResponse;
    while (
      signatureResponse === undefined ||
      signatureResponse.status !== 200
    ) {
      signatureResponse = http.post(
        signerUrl + "sign",
        JSON.stringify({
          message: challenge.credentialSubject.challenge,
          privateKey,
        }),
        options
      );
    }
    const { signature } = JSON.parse(signatureResponse.body);

    const payload = {
      address,
      type: "Simple",
      types: ["Simple", "ClearTextSimple"],
      version: "",
      proofs: {
        username: "test",
        valid: "true",
        signature,
      },
    };

    const verifyResponse = http.post(
      iamUrl + "verify",
      JSON.stringify({
        payload,
        challenge,
      }),
      trackedRequestOptions
    );

    check(verifyResponse, {
      "is status 200": (r) => r.status === 200,
    });

    if (verifyResponse.status === 200) {
      credentials = JSON.parse(verifyResponse.body).map((r) => r.credential);
    } else {
      console.log(
        "Verifying stamps failed: ",
        JSON.stringify(verifyResponse, undefined, 2)
      );
    }
  }

  // This doesn't work b/c these addresses haven't been scored.
  // But, this could be refactored and/or combined with the other
  // load test to work.
  //
  // if (credentials) {
  //   const attestationResponse = http.post(
  //     iamUrl + "eas/passport",
  //     JSON.stringify({
  //       credentials,
  //       nonce: Math.floor(Math.random() * 100000000000),
  //       chainIdHex: "0xa",
  //     }),
  //     trackedRequestOptions
  //   );
  //   if (attestationResponse.status !== 200) {
  //     console.log(
  //       "Attestation failed: ",
  //       JSON.stringify(attestationResponse, undefined, 2)
  //     );
  //   }
  // }
}
