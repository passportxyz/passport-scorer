import http from "k6/http";
import { sleep } from "k6";
import exec from "k6/execution";
import { randomSeed } from "k6";
import { check } from "k6";

randomSeed(234123521532);
function getRandomInt(max) {
  const ret = Math.floor(Math.random() * max);
  console.log("getRandomInt ", ret);
  return ret;
}

// import HDWallet from "https://cdn.jsdelivr.net/npm/ethereum-hdwallet@latest/ethereum-hdwallet.js";

// console.log("HDWallet", HDWallet)
// const mnemonic = 'tag volcano eight thank tide danger coast health above argue embrace heavy'
// const hdwallet = HDWallet.fromMnemonic(mnemonic)
// console.log(`0x${hdwallet.derive(`m/44'/60'/0'/0/0`).getAddress().toString('hex')}`) // 0xc49926c4124cee1cba0ea94ea31a6c12318df947

export const options = {
  vus: 1,
  duration: "15s",
};

// console.log("This is init code: ", exec.vu.idInInstance);
// console.log("This is init code: ", exec.vu.idInTest);

export function setup() {
  console.log("setup");
  console.log("This is setup code: ", exec.vu.idInInstance);
  console.log("This is setup code: ", exec.vu.idInTest);
}

export function teardown(data) {
  console.log("teardown");
}

const addresses = JSON.parse(open("./test_data/generated_accounts.json"));
const vcs_for_address = [];

for (let i = 0; i < 100; i++) {
  const address = addresses[i];
  const vcs = JSON.parse(open(`./test_data/vcs/${address}_vcs.json`));
  vcs_for_address.push(vcs);
}


// create k6 setup and teardown
export default function () {
  // const idx = exec.vu.idInInstance - 1;
  const token =
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNjg1NDQ4NzgxLCJpYXQiOjE2ODUzNjIzODEsImp0aSI6IjU5YTk5NDM1NTE2ODRlZmNiNDc5M2EyNDUyMDQxNGI0IiwiZGlkIjoiZGlkOnBraDplaXAxNTU6MToweDg1ZmYwMWNmZjE1NzE5OTUyNzUyODc4OGVjNGVhNjMzNjYxNWM5ODkifQ.yqAcYcozOEvf696V7_BR-bOvYCsIDm1qg1j6wnzusLA";
  console.log("This is vu info: ", exec.vu.idInInstance);

  const addressIdx = getRandomInt(100);
  const address = addresses[addressIdx];
  const vcs = vcs_for_address[addressIdx];
  console.log("address", address);

  const body = [];
  const bodyDelete = [];

  for (let j = 0; j < vcs.length; j++) {
    const stamp = vcs[j];
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

  const options = {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  };

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

  if(res.status !== 201) {
    console.log("This failed: ", JSON.stringify(res, undefined, 2));
  }
}
