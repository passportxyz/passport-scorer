'use client'
import { useState, useEffect } from 'react'
import { ethers } from 'ethers'
import { BigNumber } from "@ethersproject/bignumber";
import { ChakraProvider, Flex, Heading, Button } from '@chakra-ui/react'
import { TabLayout } from './tab-contents'
import { Attestation, SchemaEncoder } from "@ethereum-attestation-service/eas-sdk";
import { resolverAbi, EasAbi } from "./abis";
import { PROVIDER_ID, providerBitMapInfo, DecodedProviderInfo } from "./providerInfo";
import { GITCOIN_PASSPORT_WEIGHTS } from './stamp-weights';

const resolverContractAddress = "0xc0fF118369894100b652b5Bb8dF5A2C3d7b2E343";
const EasContractAddress = "0xAcfE09Fd03f7812F022FBf636700AdEA18Fd2A7A"

declare global {
  interface Window {
    ethereum: any
  }
}

declare global {
  var provider: ethers.BrowserProvider
}

interface Stamp {
  id: number
  stamp: string
}

export default function Passport() {
  // here we deal with any local state we need to manage
  const [address, setAddress] = useState<string>('default')
  const [connected, setConnected] = useState<boolean>(false)
  const [hasStamps, setHasStamps] = useState<boolean>(false)
  const [stamps, setStamps] = useState<Array<Stamp>>([])
  const [score, setScore] = useState<Number>(0)

  useEffect(() => {
    checkConnection()
    async function checkConnection() {
      if (connected) {
        console.log("already connected")
      } else {
        const result = await connect()
        console.log(result)
      }
    }
  }, [address, connected])

  async function connect() {
    try {
      globalThis.provider = new ethers.BrowserProvider(window.ethereum)
      const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' })
      setAddress(accounts[0])
      setConnected(true)
    } catch (err) {
      console.log('error connecting...')
    }
    return true
  }

  async function getUuid() {
    const resolverContract: ethers.Contract = new ethers.Contract(resolverContractAddress, resolverAbi, provider)
    const uuid = await resolverContract.passports("0xC79ABB54e4824Cdb65C71f2eeb2D7f2db5dA1fB8")
    console.log(uuid)
    if (uuid == "0x0000000000000000000000000000000000000000000000000000000000000000") {
      (console.log("no passport data on chain!"))
    } else {
      return uuid
    }
  }

  async function getAttestation(uuid: string) {
    const EasContract: ethers.Contract = new ethers.Contract(EasContractAddress, EasAbi, provider)
    const attestation = await EasContract.getAttestation(uuid)
    return attestation
  }

  async function decodeAttestation(attestation: Attestation) {
    const schemaEncoder = new SchemaEncoder(
      "uint256[] providers,bytes32[] hashes,uint64[] issuanceDates,uint64[] expirationDates,uint16 providerMapVersion"
    );
    const decodedData = schemaEncoder.decodeData(attestation.data)
    const providers = decodedData.find((data) => data.name === "providers")?.value.value as BigNumber[];
    type DecodedProviderInfo = {
      providerName: PROVIDER_ID;
      providerNumber: number;
    };
    const onChainProviderInfo: DecodedProviderInfo[] = providerBitMapInfo
      .map((info) => {
        const providerMask = BigNumber.from(1).shl(info.bit);
        const currentProvidersBitmap = providers[info.index];
        if (currentProvidersBitmap && !providerMask.and(currentProvidersBitmap).eq(BigNumber.from(0))) {
          return {
            providerName: info.name,
            providerNumber: info.index * 256 + info.bit,
          };
        }
      })
      .filter((provider): provider is DecodedProviderInfo => provider !== undefined);

    return onChainProviderInfo
  }

  function getStamps(onChainProviderInfo: DecodedProviderInfo[]) {
    const stamps: Array<Stamp> = []
    onChainProviderInfo.forEach(toArray)
    function toArray(item: any, index: number) {
      let s = { id: index, stamp: item.providerName }
      stamps.push(s)
    }
    setStamps(stamps)
    setHasStamps(stamps.length > 0)
    return stamps
  }

  async function queryPassport() {
    try {
      const uuid = await getUuid()
      const att = await getAttestation(uuid)
      const onChainProviderInfo = await decodeAttestation(att)
      const stampData = getStamps(onChainProviderInfo)
      const scoreData = calculate_score(stampData)
      setScore(scoreData)
    } catch {
      console.log("error decoding data - you might not have any data onchain!")
    }
  }

  function calculate_score(stampData: Array<Stamp>) {
    let i = 0
    var scores: Array<number> = []
    var score = 0;
    while (i < stampData.length) {
      let id = stampData[i].stamp
      if (GITCOIN_PASSPORT_WEIGHTS.hasOwnProperty(id)) {
        try {
          let temp_score = GITCOIN_PASSPORT_WEIGHTS[id]
          scores.push(parseFloat(temp_score))
        } catch {
          console.log("element cannot be added to cumulative score")
        }
      }
      i++;
    }
    for (let i = 0; i < scores.length; i++) {
      console.log("in loop")
      score += scores[i]
    }
    return score
  }

  const styles = {
    main: {
      width: '900px',
      margin: '0 auto',
      paddingTop: 90
    }
  }

  return (
    /* this is the UI for the app */
    <div style={styles.main}>
      <ChakraProvider>
        <Flex minWidth='max-content' alignItems='right' gap='2' justifyContent='right'>
          <Button colorScheme='teal' variant='outline' onClick={connect}>Connect</Button>
          <Button colorScheme='teal' variant='outline' onClick={queryPassport}>Query Passport</Button>
        </Flex>
        <br />
        <br />
        <br />
        <br />
        <Heading as='h1' size='4xl' noOfLines={2}>Onchain Stamp Explorer!</Heading>
        <br />
        <br />
        <TabLayout hasStamps={hasStamps} stamps={stamps} score={score} />
      </ChakraProvider >
    </div >
  )
}

