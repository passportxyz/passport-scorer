import {
  Input,
  Text,
} from "@chakra-ui/react";
import { KeyIcon } from "@heroicons/react/24/outline";
import { useContext, useState } from "react";
import { UserContext } from "../context/userContext";
import { ApiKeys, createApiKey } from "../utils/account-requests";
import { ApiKeyDisplay } from "./APIKeyList";
import ModalTemplate from "./ModalTemplate";

export type ApiKeyCreateModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onCreateApiKey: (keyName: ApiKeyDisplay) => void;
};

export function ApiKeyCreateModal({
  isOpen,
  onClose,
  onCreateApiKey,
}: ApiKeyCreateModalProps) {
  const [keyName, setKeyName] = useState("");
  const [creationError, setError] = useState<string>("");
  const [inProgress, setInProgress] = useState(false);
  const { setUserWarning } = useContext(UserContext);

  const closeAndReset = () => {
    setKeyName("");
    setError("");
    onClose();
  };

  const handleCreateApiKey = async () => {
    try {
      setInProgress(true);
      const apiKey: ApiKeyDisplay = await createApiKey(keyName);;
      setInProgress(false);
      setUserWarning(
        "Make sure to paste your API key somewhere safe, as it will be forever hidden after you copy it."
      );
      onCreateApiKey(apiKey);
      closeAndReset();
    } catch (error: any) {
      const msg =
        error?.response?.data?.detail ||
        "There was an error creating your API key. Please try again.";
      setError(msg);
      setInProgress(false);
    }
  };

  return (
    <ModalTemplate
      isOpen={isOpen}
      onClose={closeAndReset}
      footer={() => (
        <button
          className="mb-6 mt-auto w-full rounded bg-purple-gitcoinpurple py-3 text-white md:mt-8"
          onClick={handleCreateApiKey}
          disabled={keyName.length === 0 || inProgress}
        >
          Create
        </button>
      )}
    >
      <div className="w-100 flex flex-col items-center">
        <div className="w-fit rounded-full bg-[#F0EBFF] p-3 text-purple-gitcoinpurple">
          <div className="flex w-6 justify-around">
            <KeyIcon />
          </div>
        </div>
      </div>
      <div className="mt-6 mb-6 text-center">
        <Text className="text-purple-darkpurple">Generate API Key</Text>
        <Text className="mt-2 text-center text-purple-softpurple">
          Name your API key to help identify it in the future.
        </Text>
      </div>
      <div className="flex flex-col">
        <label className="mb-2 font-librefranklin text-xs text-purple-darkpurple">
          Key Name
        </label>
        <Input
          className="mb-6"
          data-testid="key-name-input"
          value={keyName}
          onChange={(e) => setKeyName(e.target.value)}
          placeholder={"Enter the key's name/identifier"}
          // chakra can't find purple-gitcoinpurple from tailwind :(
          focusBorderColor="#6f3ff5"
        />

        <p className="mb-1 text-xs italic text-purple-softpurple">
          i.e. &#39;Gitcoin dApp - Prod&#39;, or &#39;Snapshot discord bot&#39;,
          or &#39;Bankless Academy testing&#39;, etc.
        </p>
        <hr />
        {creationError.length > 0 && (
          <p className="pt-4 text-red-700">{creationError}</p>
        )}
      </div>
    </ModalTemplate>
  );
}

export type ApiKeyUpdateModalProps = {
  isOpen: boolean;
  apiKeyId: ApiKeys["id"];
  onClose: () => void;
  onUpdateApiKey: (apiKeyId: ApiKeys["id"], name: ApiKeys["name"]) => void;
};

export function ApiKeyUpdateModal({
  isOpen,
  apiKeyId,
  onClose,
  onUpdateApiKey,
}: ApiKeyUpdateModalProps) {
  const [name, setName] = useState("");
  const [updateError, setError] = useState<string>("");
  const [inProgress, setInProgress] = useState(false);

  const closeAndReset = () => {
    setName("");
    setError("");
    onClose();
  };

  const updateApiKey = async () => {
    setInProgress(true);
    await onUpdateApiKey(apiKeyId, name);
    setInProgress(false);
  };

  return (
    <ModalTemplate
      isOpen={isOpen}
      onClose={closeAndReset}
      header={() => (
        <span className="text-base font-normal">Rename API Key</span>
      )}
      footer={() => (
        <button
          className="mb-6 mt-auto w-full rounded bg-purple-gitcoinpurple py-3 text-white md:mt-8"
          onClick={updateApiKey}
          disabled={name.length === 0 || inProgress}
        >
          Save Changes
        </button>
      )}
    >
      <div className="flex flex-col">
        <label className="mb-2 font-librefranklin text-xs text-purple-darkpurple">
          Key Name
        </label>
        <Input
          className="mb-6"
          data-testid="key-name-input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={"Enter the key's name/identifier"}
          // chakra can't find purple-gitcoinpurple from tailwind :(
          focusBorderColor="#6f3ff5"
        />

        <p className="mb-1 text-xs italic text-purple-softpurple">
          i.e. &#39;Gitcoin dApp - Prod&#39;, or &#39;Snapshot discord bot&#39;,
          or &#39;Bankless Academy testing&#39;, etc.
        </p>
        <hr />
        {updateError.length > 0 && (
          <p className="pt-4 text-red-700">{updateError}</p>
        )}
      </div>
    </ModalTemplate>
  );
}
