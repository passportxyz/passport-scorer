// --- React components/methods
import React, { useContext, useEffect, useState } from "react";

// --- Components
import { SettingsIcon } from "@chakra-ui/icons";

// --- Utils
import {
  ApiKeys,
  getApiKeys,
  deleteApiKey,
} from "../utils/account-requests";
import NoValues from "./NoValues";
import { UserContext } from "../context/userContext";
import { ApiKeyModal } from "./ApiKeyModal";
import { CheckIcon, ClipboardDocumentIcon, EllipsisVerticalIcon } from "@heroicons/react/24/solid";
import { useToast } from "@chakra-ui/react";
import { successToast } from "./Toasts";

export type ApiKeyDisplay = ApiKeys & {
  api_key?: string;
  copied?: boolean;
};

const APIKeyList = () => {
  const [error, setError] = useState<undefined | string>();
  const [apiKeys, setApiKeys] = useState<ApiKeyDisplay[]>([]);
  const [createApiKeyModal, setCreateApiKeyModal] = useState(false);
  const { logout, setUserWarning } = useContext(UserContext);
  const toast = useToast();

  useEffect(() => {
    let keysFetched = false;
    const fetchApiKeys = async () => {
      if (keysFetched === false) {
        try {
          const apiKeys = await getApiKeys();
          keysFetched = true;
          setApiKeys(apiKeys);
        } catch (error: any) {
          setError("There was an error fetching your API keys.");
          if (error.response.status === 401) {
            logout();
          }
        }
      }
    };
    fetchApiKeys();
  }, []);

  const handleDeleteApiKey = async (apiKeyId: ApiKeys["id"]) => {
    try {
      await deleteApiKey(apiKeyId);
      setApiKeys(await getApiKeys());
    } catch (error: any) {
      if (error.response.status === 401) {
        logout();
      }
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
          <p className="py-3">Use these API keys to programmatically access a Scorer.</p>
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
                      {key.copied ? (
                        <p className="text-purple-gitcoinpurple flex text-xs">Copied! <CheckIcon height={14} color={"6f3ff5"} /></p>
                      ) : (
                        <>
                          <p className="flex text-purple-darkpurple text-xs pr-3">
                            {key.api_key}
                          </p>
                          <button
                            className="mb-1"
                            data-testid="copy-api-key"
                            onClick={async () => {
                              await navigator.clipboard.writeText(key.api_key!);
                              const updatedKeys = apiKeys.map((k) => k.api_key === key.api_key ? { ...k, copied: true } : k);
                              setApiKeys(updatedKeys);
                              setUserWarning()
                            }}
                          >
                            <ClipboardDocumentIcon height={14} color={"#0E0333"} />
                          </button>
                        </>
                      )}
                    </div>
                  )}
                  <button
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
              className="rounded-md bg-purple-gitcoinpurple px-5 py-2 text-white"
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
        onApiKeyCreated={(apiKey: ApiKeyDisplay) => {
          toast(successToast("API Key created successfully!", toast));
          setUserWarning("Make sure to paste your API key somewhere safe, as it will be forever hidden after you copy it.");
          setApiKeys([...apiKeys, apiKey]);
        }}
      />
    </>
  );
};
export default APIKeyList;
