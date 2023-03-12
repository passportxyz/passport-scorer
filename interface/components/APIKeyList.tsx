// --- React components/methods
import React, { useContext, useEffect, useState } from "react";

// --- Components
import { Input } from "@chakra-ui/react";
import ModalTemplate from "./ModalTemplate";
import { DeleteIcon, Icon } from "@chakra-ui/icons";
import { MdFileCopy } from "react-icons/md";

// --- Utils
import {
  ApiKeys,
  createApiKey,
  getApiKeys,
  deleteApiKey,
} from "../utils/account-requests";
import NoValues from "./NoValues";
import { UserContext } from "../context/userContext";
import { KeyIcon } from "@heroicons/react/24/outline";

const APIKeyList = () => {
  const [error, setError] = useState<undefined | string>();
  const [apiKeys, setApiKeys] = useState<ApiKeys[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [apiKeyModalOpen, setApiKeyModalOpen] = useState(false);
  const [newApiKey, setNewApiKey] = useState();
  const [keyName, setKeyName] = useState("");
  const { logout } = useContext(UserContext);

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

  const handleCreateApiKey = async () => {
    try {
      const apiKey = await createApiKey(keyName);
      setNewApiKey(apiKey.api_key);
      setKeyName("");
      setApiKeys(await getApiKeys());
      setModalOpen(false);
      setApiKeyModalOpen(true);
    } catch (error: any) {
      setError("There was an error creating your API key.");
      if (error.response.status === 401) {
        logout();
      }
    }
  };

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
      <div className="mx-auto mb-12 text-purple-softpurple">
        Use these API keys to programmatically access a Scorer.
      </div>
      {apiKeys.length === 0 ? (
        <div className="h-full">
          <NoValues
            title="Generate API Keys"
            description="Interact with the Scorer(s) created via your API key. The key limit is five."
            addActionText="API Key"
            addRequest={() => setModalOpen(true)}
            icon={<KeyIcon />}
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
                onClick={() => setModalOpen(true)}
              >
                <span className="mr-2 text-lg">+</span>Create a key
              </button>
            </div>
            {modalOpen}
            {error && <div>{error}</div>}

            <div className="flex items-center px-4 py-4 sm:px-6">
              <div className="min-w-0 flex-1 md:grid md:grid-cols-3 md:gap-4">
                <div>
                  <p className="my-2 text-sm text-purple-gitcoinpurple">
                    Usecase
                  </p>
                  <p className="truncate text-base font-medium text-purple-darkpurple">
                    Community Name
                  </p>
                  <p className="mt-2 flex items-center text-sm text-purple-softpurple">
                    <span className="truncate">Community Description</span>
                  </p>
                </div>
                <div className="pt-5">
                  <p className="mt-2 flex flex-row-reverse text-sm text-purple-softpurple">
                    Created:
                  </p>
                  <p className="flex flex-row-reverse text-sm text-purple-softpurple">
                    {/* {community.created_at
                      ? new Date(community.created_at).toDateString()
                      : "unknown"} */}
                    Community date
                  </p>
                </div>
                <div className="pt-5">
                  <p className="mt-2 flex flex-row-reverse text-sm text-purple-softpurple">
                    Scorer ID:
                  </p>
                  <p className="flex flex-row-reverse text-sm text-purple-softpurple">
                    12
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      <ModalTemplate
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        size={{ base: "full", md: "xl", lg: "xl", xl: "xl" }}
      >
        <div className="flex h-screen flex-col">
          <div className="w-100 flex flex-col items-center">
            <div className="mb-6 w-fit rounded-full bg-[#F0EBFF] p-3 text-purple-gitcoinpurple">
              <div className="flex w-6 justify-around">
                <KeyIcon />
              </div>
            </div>
          </div>
          <div className="mb-6 items-center text-center">
            <h2 className="text-purple-darkpurple">Generate API Key</h2>
            <p className="mt-2 text-purple-softpurple">
              Name your API key to help identify it in the future.
            </p>
          </div>
          <label className="text-gray-softgray font-librefranklin text-xs">
            Key Name
          </label>
          <Input
            data-testid="key-name-input"
            value={keyName}
            onChange={(name) => setKeyName(name.target.value)}
            placeholder="Enter the key's name/identifier"
            className="mt-2"
          />
          <p className="mt-6 mb-1 text-xs italic text-purple-softpurple">
            i.e. 'Gitcoin dApp - Prod', or 'Snapshot discord bot', or 'Bankless
            Academy testing', etc.
          </p>
          <hr />
          <button
            disabled={!keyName}
            data-testid="create-button"
            className="mt-auto mb-4 w-full rounded bg-purple-gitcoinpurple py-2 px-4 text-sm text-white disabled:opacity-25 md:mt-11"
            onClick={handleCreateApiKey}
          >
            Create
          </button>
        </div>
      </ModalTemplate>
      <ModalTemplate
        isOpen={apiKeyModalOpen}
        onClose={() => setApiKeyModalOpen(false)}
        title="Copy your API Key"
      >
        <div className="flex flex-col">
          <label className="text-gray-softgray font-librefranklin text-xs">
            API Key
          </label>
          <Input
            className="mb-6"
            data-testid="key-name-input-read"
            value={newApiKey}
            readOnly={true}
          />
        </div>
      </ModalTemplate>
      <hr className="md:hidden" />
    </>
  );
};
export default APIKeyList;
