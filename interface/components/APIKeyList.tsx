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

export const ApiKeyList = () => {
  const [apiKeys, setApiKeys] = useState<ApiKeys[]>([]);
  const [error, setError] = useState<undefined | string>();
  const [modalOpen, setModalOpen] = useState(false);
  const [apiKeyModalOpen, setApiKeyModalOpen] = useState(false);
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

  const handleCreateApiKey = async () => {
    try {
      const apiKey = await createApiKey(keyName);
      setNewApiKey(apiKey.api_key);
      setKeyName("");
      setApiKeys(await getApiKeys());
      setModalOpen(false);
      setApiKeyModalOpen(true);
    } catch (error) {
      setError("There was an error creating your API key.");
    }
  };

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
                  key={key.id}
                  className="grid grid-cols-4 gap-3 auto-cols-auto border-x border-t last-of-type:border-b first-of-type:rounded-t-md last-of-type:rounded-b-md w-full items-center justify-between border-gray-lightgray bg-white p-4 hover:bg-gray-50"
                >
                  <div className="justify-self-center md:justify-self-start font-semibold">
                    <p>{key.name}</p>
                  </div>
                  <div className="justify-self-start md:justify-self-center text-purple-softpurple">
                    <p>
                      {key.prefix.substring(0, 15)}...
                      <span>
                        <Icon
                          className="ml-1"
                          as={MdFileCopy}
                          color="#757087"
                        />
                      </span>
                    </p>
                  </div>
                  <div className="rounded-full justify-self-center bg-gray-lightgray px-3 py-1">
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
            Key name
          </label>
          <Input
            data-testid="key-name-input"
            value={newApiKey}
            readOnly={true}
          />
        </div>
      </ModalTemplate>
    </>
  );
};
