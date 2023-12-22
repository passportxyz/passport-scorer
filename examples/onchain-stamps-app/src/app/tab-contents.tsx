import React from "react"
import { Heading, Tabs, TabList, TabPanels, Tab, TabPanel, Link, SimpleGrid } from '@chakra-ui/react'

const TabLayout = ({ hasStamps, stamps, score }) => {
    return (
        <Tabs>
            <TabList>
                <Tab>Home</Tab>
                <Tab>About onchain Stamps</Tab>
                <Tab>Are your Stamps onchain?</Tab>
                <Tab>Browse your Stamps</Tab>
                <Tab>See your score</Tab>
            </TabList>
            <TabPanels>
                <TabPanel>
                    <Welcome />
                </TabPanel>
                <TabPanel>
                    <AboutOnChainStamps />
                </TabPanel>
                <TabPanel>
                    <CheckStamps hasStamps={hasStamps} />
                </TabPanel>
                <TabPanel>
                    <ShowStamps stamps={stamps} />
                </TabPanel>
                <TabPanel>
                    <ShowScore score={score} />
                </TabPanel>
            </TabPanels>
        </Tabs>
    )
}

const Welcome = () => {
    return (
        <>
            <br />
            <br />
            <p>This app demonstrates how to use Gitcoin Passport's onchain stamps.</p>
            <br />
            <p>In the <b>About onchain Stamps</b> tab you will find resources to help you understand onchain Stamps.</p>
            <br />
            <p>You can also connect your wallet to check whether you have onchain Stamps</p>
            <br />
            <li>Connect your wallet by clicking "Connect"</li>
            <li>Allow the app to query your Passport by clicking "Query Passport"</li>
            <li>Navigate to the <b>Are your Stamps onchain?</b> tab to see whether you have onchain Stamps</li>
            <li>Navigate to the <b>Browse your Stamps</b> tab to see which Stamps you own onchain!</li>
            <br />
            <p>This is just an example app to demonstrate how onchain stamps can be built into your own project.</p>

        </>
    )
}

const AboutOnChainStamps = () => {
    return (
        <>
            <br />
            <br />
            <p><b>Onchain Stamps are available to smart contracts!</b></p>
            <br />
            <p>Onchain Stamps are created using web3 primitives, meaning you are never reliant upon Gitoin's servers for access to your data. Your apps are only available to smart contract applications when they are onchain.</p>
            <br />
            <p>You can migrate your Stamps onchain any time using the Passport app.</p>
            <br />
            <p>This app is a demonstration of how onchain Stamps can be queried and used to gate content by app developers.</p>
            <p>In the background, this app is loading the relevant contracts, querying your address to check for Stamps, retrieving and decoding them.</p>
            <br />
            <p>If you have Stamps, then you will see a message of congratulations in the next tab. You will also be able to see your Stamps in the final tab.</p>
            <br />
            <p>However, if you do not have onchain Stamps, instead of the congratulatory message you will be instructed how to migrate onchain using the Passport app.</p>
        </>
    )
}

const ShowStamps = ({ stamps }) => {
    if (stamps.length > 0) {
        return (
            <>
                <br />
                <Heading as='h3' size='xl' noOfLines={2}>You have the following Stamps onchain</Heading>
                <br />
                <SimpleGrid minChildWidth='120px' spacing='40px' border='black'>
                    <>
                        {stamps.map(s => <p key={s.id}> &#9989; {s.stamp}</p>)}
                    </>
                </SimpleGrid >
            </>
        )
    } else {
        return (
            <>
                <br />
                <Heading as='h3' size='xl' noOfLines={2}>😭😭😭 You don't have any Stamps yet!</Heading>
                <br />
                <p>Maybe you haven't connected your wallet, or maybe you haven't migrated your Stamps onchain yet?</p>
                <br />
                <SimpleGrid minChildWidth='120px' spacing='40px' border='black'>
                    <>
                        {stamps.map(s => <p key={s.id}> &#9989; {s.stamp}</p>)}
                    </>
                </SimpleGrid >
            </>
        )
    }
}

const ShowScore = ({ score }) => {
    if (score > 0) {
        return (
            <>
                <br />
                <Heading as='h3' size='xl' noOfLines={2}>🎉🎉🎉 Your onchain Passport score is: {score}</Heading>
                <br />
                <p>You can improve your score by verifying more Stamps in the Passport app and migrating them onchain.</p>
            </>
        )
    } else {
        return (
            <>
                <br />
                <Heading as='h3' size='xl' noOfLines={2}>You do not yet have a score.</Heading>
                <br />
                <p>Perhaps you haven't connected your wallet, or maybe you don't have any onchain Stamps yet. You can create a Passport, add Stamps and migrate them onchain using the Passport app and migrating them onchain.</p>
            </>
        )
    }
}


const CheckStamps = ({ hasStamps }) => {
    if (hasStamps) {
        return (
            <ContentAboveThreshold />
        )
    }
    else {
        return (
            <ContentBelowThreshold />

        )
    }
}

const ContentAboveThreshold = () => {
    return (
        <>
            <br />
            <br />
            <Heading as='h3' size='xl' noOfLines={2}>🎉🎉🎉 You have onchain stamps!</Heading>
            <br />
            <p>Congratulations! We found Stamps associated with your address on the BaseGoerli network!</p>
            <br />
            <p>This means you have successfully migrated your Stamps onchain - they can be used in smart contract applications on this network!</p>
        </>
    )
}

const ContentBelowThreshold = () => {
    return (
        <>
            <br />
            <Heading as='h3' size='xl' noOfLines={2}>😭😭😭 You do not have onchain stamps!</Heading>
            <br />
            <p>Did you remember to connect and click "Query Passport?"</p>
            <br />
            <p>You can go to the <Link href="https://passport.gitcoin.co" color='teal.500' isExternal>Passport App </Link> and add more stamps to your Passport.</p>
            <p>These Stamps can then be migrated onchain with a single click!</p>
            <br />
            <p>In the meantime you can read our <Link href="https://docs.gitcoin.co" color='teal.500' isExternal> awesome documentation </Link> to learn more about Gitcoin passport</p>
        </>
    )
}

export { TabLayout };