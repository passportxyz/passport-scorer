FROM node:18.14-alpine

# Set the working directory to /app
WORKDIR /app

RUN apk add --no-cache git

COPY package.json yarn.lock ./

ENV NODE_ENV=development

# Copy package.json and package-lock.json to the working directory
COPY package*.json ./

# Install app dependencies
RUN yarn install

# Copy the rest of the application code to the working directory
COPY ../. ./

# Build the Next.js app
WORKDIR /app/interface

# Expose port 3001 to the outside world
EXPOSE 3001
