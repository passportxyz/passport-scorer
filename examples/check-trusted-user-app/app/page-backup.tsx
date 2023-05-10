'use client'
import { useState, useEffect } from 'react'
import { ethers } from 'ethers'

const APIKEY = process.env.NEXT_PUBLIC_GC_API_KEY
const SCORERID = process.env.NEXT_PUBLIC_GC_SCORER_ID

// endpoint for submitting passport
const SUBMIT_PASSPORT_URI = 'https://api.scorer.gitcoin.co/registry/submit-passport'
// endpoint for getting the signing message
const SIGNING_MESSAGE_URI = 'https://api.scorer.gitcoin.co/registry/signing-message'
// score needed to see hidden message
const thresholdNumber = 20
const headers = APIKEY ? ({
  'Content-Type': 'application/json',
  'X-API-Key': APIKEY
}) : undefined

declare global {
  interface Window {
    ethereum?: any
  }
}

// interface UserStruct {
//   id: number;
//   address: string;
//   score: number;
//   stampProviders: Array<String>;
// }

export default function Passport() {
  // here we deal with any local state we need to manage
  const [address, setAddress] = useState<string>('')
  // const [userInfo, setUserInfo] = useState<Array<UserStruct>>([])
  // const [trustedUsers, setTrustedUsers] = useState<Array<UserStruct>>([])
  // const [showTrusted, setShowTrusted] = useState<boolean>(false)

  // async function checkPassport(currentAddress = address) {
  //   console.log("in checkPassport()")
  //   let score: number = await getPassportScore(currentAddress) as number
  //   let stampProviders = await getPassportStamps(currentAddress) as Array<string>
  //   const id = userInfo.length + 1
  //   let user: UserStruct = { id: id, address: currentAddress, score: score, stampProviders: stampProviders }
  //   setUserInfo(userInfo.concat(user))
  // }


  // async function getPassportStamps(currentAddress: string) {
  //   console.log("in getStamps()")
  //   const stampProviderArray = []
  //   const GET_PASSPORT_STAMPS_URI = `https://api.scorer.gitcoin.co/registry/stamps/${currentAddress}`
  //   try {
  //     const response: Response = await fetch(GET_PASSPORT_STAMPS_URI, { headers })
  //     const data = await response.json()
  //     // parse stamp data from json
  //     for (const i of data.items) {
  //       stampProviderArray.push(i.credential.credentialSubject.provider)
  //     }
  //     return stampProviderArray
  //   } catch (err) {
  //     console.log('error: ', err)
  //   }
  // }

  // async function getPassportScore(currentAddress: string) {
  //   console.log("in getScore()")
  //   const GET_PASSPORT_SCORE_URI = `https://api.scorer.gitcoin.co/registry/score/${SCORERID}/${currentAddress}`
  //   try {
  //     const response = await fetch(GET_PASSPORT_SCORE_URI, {
  //       headers
  //     })
  //     const passportData = await response.json()
  //     if (passportData.score) {
  //       // if the user has a score, round it and set it in the local state
  //       const roundedScore = Math.round(passportData.score * 100) / 100
  //       return roundedScore
  //     } else {
  //       // if the user has no score, display a message letting them know to submit thier passporta
  //       console.log('No score available, please add stamps to your passport and then resubmit.')
  //     }
  //   } catch (err) {
  //     console.log('error: ', err)
  //   }
  // }


  useEffect(() => {
    checkConnection()
    async function checkConnection() {
      try {
        const provider = new ethers.BrowserProvider(window.ethereum)
        const accounts = await provider.listAccounts()
        // if the user is connected, set their account and fetch their score
        if (accounts && accounts[0]) {
          setAddress(accounts[0].address)
          // checkPassport(accounts[0].address)
        }
      } catch (err) {
        console.log('not connected...')
      }
    }
  }, [])


  async function connect() {
    console.log("in connect func")
    try {
      const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' })
      setAddress(accounts[0])
      // checkPassport(accounts[0])
    } catch (err) {
      console.log('error connecting...')
    }
  }


  async function getSigningMessage() {
    try {
      const response = await fetch(SIGNING_MESSAGE_URI, {
        headers
      })
      const json = await response.json()
      return json
    } catch (err) {
      console.log('error: ', err)
    }
  }

  async function submitPassport() {
    try {
      // call the API to get the signing message and the nonce
      const { message, nonce } = await getSigningMessage()
      const provider = new ethers.BrowserProvider(window.ethereum)
      const signer = await provider.getSigner()
      // ask the user to sign the message
      const signature = await signer.signMessage(message)

      // call the API, sending the signing message, the signature, and the nonce
      const response = await fetch(SUBMIT_PASSPORT_URI, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          address,
          scorer_id: SCORERID,
          signature,
          nonce
        })
      })

      const data = await response.json()
      console.log('data:', data)
    } catch (err) {
      console.log('error: ', err)
    }
  }


  // const updateShowTrusted = () => {
  //   setTrustedUsers(checkTrustedUsers())
  //   if (showTrusted === false) {
  //     setShowTrusted(true)
  //   } else {
  //     setShowTrusted(false)
  //   }
  // }

  // function checkTrustedUsers() {
  //   return userInfo.filter(
  //     user => user.stampProviders.includes('Lens')
  //       && (user.stampProviders.includes("Github"))
  //       && (user.score > 20))
  // }


  const styles = {
    main: {
      width: '900px',
      margin: '0 auto',
      paddingTop: 90
    },
    heading: {
      fontSize: 60
    },
    intro: {
      fontSize: 18,
      color: 'rgba(0, 0, 0, .55)'
    },
    configurePassport: {
      marginTop: 20,
    },
    linkStyle: {
      color: '#008aff'
    },
    buttonContainer: {
      marginTop: 20
    },
    buttonStyle: {
      padding: '10px 30px',
      outline: 'none',
      border: 'none',
      cursor: 'pointer',
      marginRight: '10px',
      borderBottom: '2px solid rgba(0, 0, 0, .2)',
      borderRight: '2px solid rgba(0, 0, 0, .2)'
    },
    hiddenMessageContainer: {
      marginTop: 15
    },
    noScoreMessage: {
      marginTop: 20
    }
  }

  return (
    /* this is the UI for the app */
    <div style={styles.main}>
      <h1 style={styles.heading}>Are you a trusted user? 🫶</h1>
      <p style={styles.configurePassport}>Configure your passport <a style={styles.linkStyle} target="_blank" href="https://passport.gitcoin.co/#/dashboard">here</a></p>
      <p style={styles.configurePassport}>Once you've added more stamps to your passport, submit your passport again to recalculate your score.</p>
      <p style={styles.configurePassport}>If you have a score above 20, a Github stamp AND a Lens stamp, you are a trusted user! Click the Check Users button to find out!</p>
      <div style={styles.buttonContainer}>
        <div style={styles.buttonContainer}>
          <button style={styles.buttonStyle} onClick={connect}>Connect</button>
          <button style={styles.buttonStyle} onClick={submitPassport}>Submit Passport</button>
          {/* <button style={styles.buttonStyle} onClick={updateShowTrusted}>Check Users</button> */}
        </div>
      </div>
      {/* <div>
        <br></br>
        {showTrusted && trustedUsers.map(user => user.address)}
        {showTrusted && " is a trusted user"}
      </div> */}
    </div>
  )
}
