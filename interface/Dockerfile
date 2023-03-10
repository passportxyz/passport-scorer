FROM node:18.14-alpine

# Set the working directory to /app
WORKDIR /app

# Copy package.json and package-lock.json to the working directory
COPY package*.json ./

# Install app dependencies
RUN yarn install

# Copy the rest of the application code to the working directory
COPY . .

# Build the Next.js app
RUN yarn build

# Expose port 3000 to the outside world
EXPOSE 3000

# Set the command to start the app
CMD [ "yarn", "start" ]
