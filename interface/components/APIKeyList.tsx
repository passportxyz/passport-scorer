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
import { ClipboardDocumentIcon, EllipsisVerticalIcon } from "@heroicons/react/24/solid";

export type ApiKeyDisplay = ApiKeys & {
  api_key?: string;
};

const APIKeyList = () => {
  const [error, setError] = useState<undefined | string>();
  const [apiKeys, setApiKeys] = useState<ApiKeyDisplay[]>([]);
  const [createApiKeyModal, setCreateApiKeyModal] = useState(false);

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
        <>
          <div className="flex w-full flex-col">
            {apiKeys.map((key, i) => (
              <div
                key={`${key.id}-${i}`}
                className="flex w-full items-center justify-between border-x border-t border-gray-lightgray bg-white p-4 first-of-type:rounded-t-md last-of-type:rounded-b-md last-of-type:border-b hover:bg-gray-50"
              >
                <div className="justify-self-center text-purple-darkpurple md:justify-self-start">
                  <p>{key.name}</p>
                </div>

                <div className="flex">
                  {key.api_key && (
                    <div className="flex mt-1.5 pr-5">
                      <p className="flex text-purple-darkpurple text-xs pr-3">
                        {key.api_key}
                      </p>
                      <ClipboardDocumentIcon height={14} color={"#0E0333"} />
                    </div>
                  )}
                  <button
                    className="justify-self-end rounded-md"
                    onClick={async () => await handleDeleteApiKey(key.id)}
                  >
                    <EllipsisVerticalIcon height={25} color={"#0E0333"} />
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div className="flex items-center py-4">
            <button
              data-testid="open-api-key-modal"
              className="rounded bg-gray-lightgray py-2 px-4 text-purple-darkpurple"
              onClick={() => setCreateApiKeyModal(true)}
            >
              <span className="mr-2 text-lg">+</span>API Key
            </button>
            <p className="pl-4 text-xs text-purple-softpurple">
              The key limit is five.
            </p>
          </div>
          {createApiKeyModal}
          {error && <div>{error}</div>}
        </>
      )}
      <ApiKeyModal
        isOpen={createApiKeyModal}
        onClose={() => setCreateApiKeyModal(false)}
        onApiKeyCreated={(apiKey: ApiKeyDisplay) =>
          setApiKeys([...apiKeys, apiKey])
        }
      />
    </>
  );
};
export default APIKeyList;
