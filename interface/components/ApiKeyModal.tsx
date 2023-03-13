import { ArrowBackIcon, SmallCloseIcon } from "@chakra-ui/icons";
import { Center, Input, Text } from "@chakra-ui/react";
import { KeyIcon } from "@heroicons/react/24/outline";
import Image from "next/image";
import { useState } from "react";
import { ApiKeys, createApiKey } from "../utils/account-requests";
import ModalTemplate from "./ModalTemplate";
import { PrimaryBtn } from "./PrimrayBtn";

export type ApiKeyModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onApiKeyCreated: (apiKey: ApiKeys) => void;
};

export function ApiKeyModal({
  isOpen,
  onClose,
  onApiKeyCreated,
}: ApiKeyModalProps) {
  const [keyName, setKeyName] = useState("");
  const [creationError, setError] = useState<string>("");

  const closeAndReset = () => {
    setKeyName("");
    setError("");
    onClose();
  }

  const handleCreateApiKey = async () => {
    try {
      const apiKeyResponse = await createApiKey(keyName);
      onApiKeyCreated(apiKeyResponse);
      closeAndReset();
    } catch (error: any) {
      const msg =
        error?.response?.data?.detail ||
        "There was an error creating your API key. Please try again.";
      setError(msg);
    }
  };

  return (
    <ModalTemplate isOpen={isOpen} onClose={closeAndReset}>
      <>
        <div className="w-100 flex flex-col items-center">
          <div className="mb-6 w-fit rounded-full bg-[#F0EBFF] p-3 text-purple-gitcoinpurple">
            <div className="flex w-6 justify-around">
              <KeyIcon />
            </div>
          </div>
        </div>
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

        <p className="text-xs text-purple-softpurple italic">
          i.e. ‘Gitcoin dApp - Prod’, or ‘Snapshot discord bot’, or ‘Bankless
          Academy testing’, etc.
        </p>
        <hr />
        {creationError.length > 0 && (
          <p className="pt-4 text-red-700">{creationError}</p>
        )}
        <PrimaryBtn
          onClick={handleCreateApiKey}
          disabled={keyName.length === 0}
        >
          Create
        </PrimaryBtn>
      </div>
    </ModalTemplate>
  );
}
