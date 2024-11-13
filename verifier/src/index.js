const express = require("express");
const cors = require("cors");
const ethers = require("ethers");
const caip = require("caip");
const app = express();

import("dids").then((dids) => {
  import("@didtools/cacao").then((didtools) => {
    import("multiformats/cid").then((multiformats) => {
      import("key-did-resolver").then((KeyResolver) => {
        const DID = dids.DID;
        const Cacao = didtools.Cacao;
        const CID = multiformats.CID;

        app.get("/verifier/health", (req, res) => {
          res.json({ health: "ok" });
        });

        app.post("/verifier/verify", (req, res) => {
          const jws_restored = {
            signatures: req.body.signatures,
            payload: req.body.payload,
            cid: CID.decode(new Uint8Array(req.body.cid)),
          };

          if (!req.body.issuer || req.body.issuer === "") {
            res.status(400);
            const msg = "Verification failed, 'issuer' is required in body!";
            console.error(msg);
            res.json({ status: "failed", error: msg });
            return;
          }

          Cacao.fromBlockBytes(new Uint8Array(req.body.cacao)).then((cacao) => {
            const recoveredAddress = ethers
              .verifyMessage(
                didtools.SiweMessage.fromCacao(cacao).toMessage(),
                cacao.s.s
              )
              .toLowerCase();
            const recoveredAddresses = [recoveredAddress];
            if (
              Date.parse(cacao.p.iat) <= didtools.LEGACY_CHAIN_ID_REORG_DATE
            ) {
              const legacyChainIdRecoveredAddress = ethers
                .verifyMessage(
                  didtools.asLegacyChainIdString(
                    didtools.SiweMessage.fromCacao(cacao),
                    "Ethereum"
                  ),
                  cacao.s.s
                )
                .toLowerCase();
              recoveredAddresses.push(legacyChainIdRecoveredAddress);
            }
            const issuerAddress = caip.AccountId.parse(
              cacao.p.iss.replace("did:pkh:", "")
            ).address.toLowerCase();

            console.log(`Recovered addresses: ${recoveredAddresses}`);
            console.log(`Issuer address: ${issuerAddress}`);

            const did = new DID({
              resolver: KeyResolver.getResolver(),
            });
            did
              .verifyJWS(jws_restored, {
                issuer: req.body.issuer,
                capability: cacao,
                disableTimecheck: true,
              })
              .then((verifyResult) => {
                console.log("Verification ok!");
                res.json({ status: "ok" });
              })
              .catch((error) => {
                res.status(400);
                console.error("Verification failed :( - ", error);
                res.json({ status: "failed", error: error.toString() });
              });
          });
        });
      });
    });
  });
});

// parse JSON post bodys
app.use(express.json());

// set cors to accept calls from anywhere
app.use(cors());

// default port to listen on
const port = process.env.VERIFIER_PORT || 8001;

app.listen(port, () => {
  // eslint-disable-next-line no-console
  console.log(`server started at http://localhost:${port}`);
});
