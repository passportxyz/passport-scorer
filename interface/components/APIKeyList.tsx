// --- React components/methods
import React, { useEffect, useState } from "react";

// --- Components
import { Input } from "@chakra-ui/react";
import ModalTemplate from "./ModalTemplate";
import { SettingsIcon, DeleteIcon, Icon } from "@chakra-ui/icons";
import { MdFileCopy } from "react-icons/md";

// --- Utils
import {
  ApiKeys,
  createApiKey,
  getApiKeys,
  deleteApiKey,
} from "../utils/account-requests";
import NoValues from "./NoValues";
import { ApiKeyModal } from "./ApiKeyModal";

const APIKeyList = () => {
  const [error, setError] = useState<undefined | string>();
  const [apiKeys, setApiKeys] = useState<ApiKeys[]>([]);
  const [createApiKeyModal, setCreateApiKeyModal] = useState(false);
  const [newApiKey, setNewApiKey] = useState();
  const [keyName, setKeyName] = useState("");

  useEffect(() => {
    let keysFetched = false;
    const fetchApiKeys = async () => {
      if (keysFetched === false) {
        try {
          const apiKeys = await getApiKeys();
          keysFetched = true;
          setApiKeys(apiKeys);
        } catch (error) {
          console.log({ error });
          setError("There was an error fetching your API keys.");
        }
      }
    };
    fetchApiKeys();
  }, []);

  const handleDeleteApiKey = async (apiKeyId: ApiKeys["id"]) => {
    try {
      await deleteApiKey(apiKeyId);
      setApiKeys(await getApiKeys());
    } catch (error) {
      console.error(error);
    }
  };

  if (error) {
    return <div>{error}</div>;
  }

  return (
    <>
      {apiKeys.length === 0 ? (
        <div className="h-full">
          <div className="mx-auto text-center text-purple-softpurple">
            The API’s keys are unique to your wallet address and can be used to
            access created Scorers.
          </div>
          <NoValues
            title="Create a key"
            description="Communicate between applications by connecting a key to request service from the community or organization."
            addActionText="API Key"
            addRequest={() => setCreateApiKeyModal(true)}
            icon={<SettingsIcon />}
          />
        </div>
      ) : (
        <div className="flex">
          <div className="flex w-full">
            <div className="flex w-3/4 flex-col">
              {apiKeys.map((key, i) => (
                <div
                  key={`${key.id}-${i}`}
                  className="grid w-full auto-cols-auto grid-cols-4 items-center justify-between gap-3 border-x border-t border-gray-lightgray bg-white p-4 first-of-type:rounded-t-md last-of-type:rounded-b-md last-of-type:border-b hover:bg-gray-50"
                >
                  <div className="justify-self-center font-semibold md:justify-self-start">
                    <p>{key.name}</p>
                  </div>
                  <div className="justify-self-center rounded-full bg-gray-lightgray px-3 py-1">
                    <p>Connected</p>
                  </div>
                  <button
                    className="justify-self-end rounded-md border border-gray-lightgray bg-white px-3 pt-1 pb-2 shadow-sm shadow-gray-100"
                    onClick={async () => await handleDeleteApiKey(key.id)}
                  >
                    <DeleteIcon color="#757087" />
                  </button>
                </div>
              ))}
            </div>
            <div className="flex w-1/4 flex-col p-4">
              <button
                data-testid="open-api-key-modal"
                className="rounded bg-purple-softpurple py-2 px-4 text-white"
                onClick={() => setCreateApiKeyModal(true)}
              >
                <span className="mr-2 text-lg">+</span>Create a key
              </button>
            </div>
            {createApiKeyModal}
            {error && <div>{error}</div>}
          </div>
        </div>
      )}
      <ApiKeyModal
        isOpen={createApiKeyModal}
        onClose={() => setCreateApiKeyModal(false)}
        onApiKeyCreated={(apiKey: ApiKeys) => setApiKeys([...apiKeys, apiKey])}
      />
    </>
  );
};
export default APIKeyList;
