// --- React components/methods
import React, { useContext, useEffect, useState } from "react";

// --- Components
import { ChevronDownIcon, Icon, SettingsIcon } from "@chakra-ui/icons";

// --- Utils
import {
  ApiKeys,
  getApiKeys,
  deleteApiKey,
  createApiKey,
} from "../utils/account-requests";
import NoValues from "./NoValues";
import { UserContext } from "../context/userContext";
import { ApiKeyCreateModal } from "./ApiKeyModals";
import {
  CheckIcon,
  ClipboardDocumentIcon,
  EllipsisVerticalIcon,
  PlusIcon,
} from "@heroicons/react/24/solid";
import {
  Button,
  IconButton,
  Menu,
  MenuButton,
  MenuItem,
  MenuList,
  useToast,
} from "@chakra-ui/react";
import { successToast } from "./Toasts";
import { KeyIcon } from "@heroicons/react/24/outline";

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

  const handleCreateApiKey = async (keyName: ApiKeys["name"]) => {
    try {
      const apiKey: ApiKeyDisplay = await createApiKey(keyName);
      setCreateApiKeyModal(false);
      toast(successToast("API Key created successfully!", toast));
      setUserWarning(
        "Make sure to paste your API key somewhere safe, as it will be forever hidden after you copy it."
      );
      setApiKeys([...apiKeys, apiKey]);
    } catch (error: any) {
      const msg =
        error?.response?.data?.detail ||
        "There was an error creating your API key. Please try again.";
      setError(msg);
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
      {apiKeys.length === 0 ? (
        <div className="h-full">
          <div className="mx-auto text-center text-purple-softpurple">
            The API's keys are unique to your wallet address and can be used to
            access created Scorers.
          </div>
          <NoValues
            title="Generate API Keys"
            description="Interact with the Scorer(s) created via your API key. The key limit is five."
            addActionText="API Key"
            addRequest={() => setCreateApiKeyModal(true)}
            icon={<KeyIcon />}
          />
        </div>
      ) : (
        <>
          <p className="pb-6">
            Use these API keys to programmatically access a Scorer.
          </p>
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
                    <div className="mt-1.5 flex items-center pr-5">
                      {key.copied ? (
                        <p className="flex text-xs text-purple-gitcoinpurple">
                          Copied! <CheckIcon className="ml-3 w-3.5" />
                        </p>
                      ) : (
                        <>
                          <p className="flex pr-3 text-xs text-purple-darkpurple">
                            {key.api_key}
                          </p>
                          <button
                            className="mb-1"
                            data-testid="copy-api-key"
                            onClick={async () => {
                              await navigator.clipboard.writeText(key.api_key!);
                              const updatedKeys = apiKeys.map((k) =>
                                k.api_key === key.api_key
                                  ? { ...k, copied: true }
                                  : k
                              );
                              setApiKeys(updatedKeys);
                              setUserWarning();
                            }}
                          >
                            <ClipboardDocumentIcon
                              height={14}
                              color={"#0E0333"}
                            />
                          </button>
                        </>
                      )}
                    </div>
                  )}
                  <Menu>
                    <MenuButton
                      as={IconButton}
                      icon={
                        <EllipsisVerticalIcon className="h-8 text-purple-darkpurple" />
                      }
                      variant="ghost"
                      _hover={{ bg: "transparent" }}
                      _expanded={{ bg: "transparent" }}
                      _focus={{ bg: "transparent" }}
                    />
                    <MenuList color={"#0E0333"}>
                      <MenuItem
                        onClick={() => {
                          setCreateApiKeyModal(true);
                        }}
                      >
                        Rename
                      </MenuItem>
                      <MenuItem
                        onClick={async () => await handleDeleteApiKey(key.id)}
                      >
                        Delete
                      </MenuItem>
                    </MenuList>
                  </Menu>
                </div>
              </div>
            ))}
          </div>
          <div className="my-4 flex items-center md:my-6">
            <button
              data-testid="open-api-key-modal"
              className="rounded-md bg-purple-gitcoinpurple px-4 py-2 align-middle text-white"
              onClick={() => setCreateApiKeyModal(true)}
            >
              <PlusIcon className="mr-2 inline w-6 align-middle" />
              API Key
            </button>
            <p className="ml-6 text-xs text-purple-softpurple">
              The key limit is five.
            </p>
          </div>
          {createApiKeyModal}
          {error && <div>{error}</div>}
        </>
      )}
      <ApiKeyCreateModal
        isOpen={createApiKeyModal}
        onClose={() => setCreateApiKeyModal(false)}
        onCreateApiKey={handleCreateApiKey}
      />
    </>
  );
};
export default APIKeyList;
