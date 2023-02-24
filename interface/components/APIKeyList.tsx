// --- React components/methods
import React, { useContext, useEffect, useState } from "react";

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
import { UserContext } from "../context/userContext";

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
          console.log({ error });
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
      console.error(error);
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
        <NoValues
          title="Create a key"
          description="Communicate between applications by connecting a key to request service from the community or organization."
          addRequest={() => setModalOpen(true)}
          icon={
            <SettingsIcon
              viewBox="-2 -2 18 18"
              boxSize="1.9em"
              color="#757087"
            />
          }
        />
      ) : (
        <div className="flex h-[40rem] md:h-[45rem]">
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
          </div>
        </div>
      )}
      <ModalTemplate
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Create a key"
      >
        <div className="flex flex-col">
          <label className="text-gray-softgray font-librefranklin text-xs">
            Key name
          </label>
          <Input
            data-testid="key-name-input"
            value={keyName}
            onChange={(name) => setKeyName(name.target.value)}
            placeholder="Key name"
          />
          <div className="flex w-full justify-end">
            <button
              disabled={!keyName}
              data-testid="create-button"
              className="mt-6 mb-2 rounded bg-purple-softpurple py-2 px-4 text-white disabled:opacity-25"
              onClick={handleCreateApiKey}
            >
              Create
            </button>
          </div>
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
    </>
  );
};
export default APIKeyList;
