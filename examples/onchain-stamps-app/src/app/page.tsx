'use client'
import { useState, useEffect } from 'react'
import { ethers } from 'ethers'
import { ChakraProvider, Flex, Heading, Button } from '@chakra-ui/react'
import { TabLayout } from './tab-contents'
import { GITCOIN_PASSPORT_WEIGHTS } from './stamp-weights';

const decoderContractAddress = "0xa652BE6A92c7efbBfEEf6b67eEF10A146AAA8ADc";
const abi = require('./PassportDecoderABI.json')

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
  const [network, setNetwork] = useState<string>('')

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
      const network = await provider.getNetwork()
      setAddress(accounts[0])
      setConnected(true)
      setNetwork(network.chainId.toString())
    } catch (err) {
      console.log('error connecting...')
    }
    return true
  }


  async function getPassportInfo() {
    const decoderContract: ethers.Contract = new ethers.Contract(decoderContractAddress, new ethers.Interface(abi['0x1a4']), provider)
    const passportInfo: [] = await decoderContract.getPassport(address) // test address '0x85fF01cfF157199527528788ec4eA6336615C989'
    if (passportInfo.length > 1) {
      setHasStamps(true)
    }
    return passportInfo
  }


  async function getStamps(passportInfo: []) {
    var stamps: Stamp[] = [];
    for (var i = 0; i < passportInfo.length; i++) {
      stamps.push({ id: i, stamp: passportInfo[i][0] })
    }
    setStamps(stamps)
    return stamps
  }

  async function queryPassport() {
    const passportInfo = await getPassportInfo()
    const stamps = await getStamps(passportInfo);
    const score = calculate_score(stamps)
    setScore(score)
  }

  function calculate_score(stampData: Array<Stamp>) {
    let i = 0
    var scores: Array<number> = []
    let names = stampData.map(entry => entry.stamp);

    names.forEach(name => {
      if (GITCOIN_PASSPORT_WEIGHTS.hasOwnProperty(name)) {
        let key = name as keyof Object;
        let value = GITCOIN_PASSPORT_WEIGHTS[key].toString();
        scores.push(parseFloat(value))
      }
    })

    const totalScore = scores.reduce((acc, currentScore) => acc + currentScore, 0)

    return totalScore
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
        <div>
          {connected && <p>✅ Wallet connected</p>}
          {connected && network == "84531" && <p>✅ network: BaseGoerli</p>}
          {connected && network != "84531" && <p>🔴 Please switch to BaseGoerli network</p>}
        </div>
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

