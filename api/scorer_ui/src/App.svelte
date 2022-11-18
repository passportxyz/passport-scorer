<script lang="ts">
  import Wallet from "./lib/Wallet.svelte";
  import { address } from "./stores";
  import { PassportReader } from "@gitcoinco/passport-sdk-reader";
  import axios from "axios";
  const reader = new PassportReader();
  let currentAddress;
  let did;
  let passportLoadingState: string | null = null;
  let passportSubmissionState: string | null = null;
  let passport: any = null;
  let scores = [];

  const unsubscribe = address.subscribe((value) => {
    currentAddress = value;
    did = "did:pkh:eip155:1:" + currentAddress;
  });

  function loadPassport() {
    passportLoadingState = "Loading ...";
    console.log("Load passport");

    reader.getPassport(currentAddress).then((result) => {
      console.log("Passport:", result);
      passport = result;
      passportLoadingState = "Passport was loaded!";
    });
  }

  function submitPassport() {
    passportSubmissionState = "Submitting passport";
    axios
      .post(`${import.meta.env.VITE_SCORER_API_ENDPOINT}registry/api/submit-passport/`, {
        did: did,
        stamps: passport.stamps,
      })
      .then(function (response) {
        passportSubmissionState = "Submission done, getting updated scores";
        // handle success
        console.log(response);
        const affected_passports = response.data.affected_passports as number[];
        console.log("affected_passports", affected_passports);

        axios
          .get(`${import.meta.env.VITE_SCORER_API_ENDPOINT}scorer_weighted/api/score/`, {
            params: {
              passport_id__in: affected_passports.join(","),
            },
          })
          .then(function (response) {
            passportSubmissionState = "Received updated scores";
            console.log(response.data);
            scores = response.data;
          })
          .catch(function (error) {
            passportSubmissionState = "Error while getting updated scores";
            // handle error
            console.log(error);
          });
      })
      .catch(function (error) {
        passportSubmissionState = "Error while submitting";
        // handle error
        console.log(error);
      })
      .then(function () {
        // always executed
      });
  }
</script>

<main>
  <Wallet />
  You are connected with:
  <pre>{currentAddress}</pre>
  <div>
    <button on:click={loadPassport}>Load Passport</button>
  </div>
  {#if passportLoadingState}
    <div>{passportLoadingState}</div>
  {/if}
  <div>
    <button on:click={submitPassport}>Submit Passport</button>
  </div>
  {#if passportSubmissionState}
    <div>{passportSubmissionState}</div>
  {/if}
  {#if scores.length > 0}
    <div>
      Scores:
      <ul>
        {#each scores as score}
          <li>
            {score.passport.did}: {score.score}
          </li>
        {/each}
      </ul>
    </div>
  {/if}
</main>

<style>
  .logo {
    height: 6em;
    padding: 1.5em;
    will-change: filter;
  }
  .logo:hover {
    filter: drop-shadow(0 0 2em #646cffaa);
  }
  .logo.svelte:hover {
    filter: drop-shadow(0 0 2em #ff3e00aa);
  }
  .read-the-docs {
    color: #888;
  }
</style>
