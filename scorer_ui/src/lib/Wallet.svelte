<script lang="ts">
  import Onboard from "@web3-onboard/core";
  import injectedModule from "@web3-onboard/injected-wallets";
  //   import { ethers } from "ethers";
  import { address } from "../stores";

  const MAINNET_RPC_URL =
    "https://mainnet.infura.io/v3/7e713cef2bdb49988a13d62ed2a08280";

  const injected = injectedModule();

  const onboard = Onboard({
    wallets: [injected],
    chains: [
      {
        id: "0x1",
        token: "ETH",
        label: "Ethereum Mainnet",
        rpcUrl: MAINNET_RPC_URL,
      },
    ],
  });

  async function initWallet() {
    console.log("initing wallet ...");
    const wallets = await onboard.connectWallet();

    console.log(wallets);
    if (wallets[0] && wallets[0].accounts[0]) {
      address.update(() => wallets[0].accounts[0].address);
    }
    // if (wallets[0]) {
    //   // create an ethers provider with the last connected wallet provider
    //   const ethersProvider = new ethers.providers.Web3Provider(
    //     wallets[0].provider,
    //     "any"
    //   );

    // //   const signer = ethersProvider.getSigner();

    // //   // send a transaction with the ethers provider
    // //   const txn = await signer.sendTransaction({
    // //     to: "0x",
    // //     value: 100000000000000,
    // //   });

    // //   const receipt = await txn.wait();
    // //   console.log(receipt);
    // }
  }

  initWallet();
</script>
<!-- 
<div>This is the Wallet ...</div> -->
