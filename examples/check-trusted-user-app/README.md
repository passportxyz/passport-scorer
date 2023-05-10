
## Gitcoin Passport Trusted User App

This is a simple demo app that shows how to use the Scorer API to retrieve user scores and stamps
from Gitcoin passport. The app is built in Nextjs using `create-next-app` and Chakra-UI.

## Getting Started


Start by creating a new Nextjs project:

```sh
npx create-next-app passport-app
```

This will create a new directory called `passport-app` and populate it with several sub-directories
and files that form the skeleton of our app. `create-next-app` will ask for yes/no responses to a series of configuration questions - answer as follows:

```sh
npx create-next-app my-passport-app

✔ Would you like to use TypeScript with this project? … Yes
✔ Would you like to use ESLint with this project? … Yes
✔ Would you like to use Tailwind CSS with this project? … No
✔ Would you like to use `src/` directory with this project? … No
✔ Would you like to use experimental `app/` directory with this project? …Yes
✔ What import alias would you like configured? … @/*
```

Next, change to the new my-passport-app directory and install ethers:

`npm install ethers`

This tutorial will also use Chakra-UI for styling, so install it using npm:

```sh
npm i @chakra-ui/react @emotion/react @emotion/styled framer-motion
```

Then, run the app locally using the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You will need a web3 wallet, ideally one that already owns a Gitcoin Passport with several
stamps.Otherwise, you won't be able to do very much with this app!

## Learn More

There is a walkthrough tutorial for this app coming soon...

