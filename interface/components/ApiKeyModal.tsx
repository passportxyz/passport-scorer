import { ArrowBackIcon, SmallCloseIcon } from "@chakra-ui/icons";
import { Center, Input, Text } from "@chakra-ui/react";
import Image from "next/image";
import { useState } from "react";
import ModalTemplate from "./ModalTemplate";
import { PrimaryBtn } from "./PrimrayBtn";

export type ApiKeyModalProps = {
  isOpen: boolean;
  onClose: () => void;
};

export function ApiKeyModal({ isOpen, onClose }: ApiKeyModalProps) {
  const [keyName, setKeyName] = useState("");
  return (
    <ModalTemplate isOpen={isOpen} onClose={onClose}>
      <>
        <Center>
          <img
            src="/assets/api-key-logo.svg"
            alt="API Key Logo"
            width={50}
            height={50}
          />
        </Center>
        <Center className="mt-6">
          <Text className="text-purple-darkpurple">Generate API Key</Text>
        </Center>
        <Center className="mt-2 mb-4">
          <Text className="text-purple-softpurple">
            Name your API key to help identify it in the future.
          </Text>
        </Center>
      </>
      <div className="flex flex-col">
        <label className="text-gray-softgray pb-2 font-librefranklin text-xs">
          Key Name
        </label>
        <Input
          className="mb-6"
          data-testid="key-name-input"
          value={keyName}
          onChange={(e) => setKeyName(e.target.value)}
          placeholder={"Enter the key’s name/identifier"}
          // chakra cant find purple-gitcoinpurple from tailwind :(
          focusBorderColor="#6f3ff5"
        />

        <p className="text-xs text-purple-softpurple">
          i.e. ‘Gitcoin dApp - Prod’, or ‘Snapshot discord bot’, or ‘Bankless
          Academy testing’, etc.
        </p>
        <hr />
        <PrimaryBtn
          onClick={() => console.log("creating")}
          disabled={keyName.length === 0}
        >
          Create
        </PrimaryBtn>
      </div>
    </ModalTemplate>
  );
}
