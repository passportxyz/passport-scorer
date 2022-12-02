// --- React components/methods
import { Input } from "@chakra-ui/react";
import React, { useEffect, useState } from "react";
import { ApiKeys, createApiKey, getApiKeys, deleteApiKey } from "../utils/account-requests";
import ModalTemplate from "./ModalTemplate";
import { DeleteIcon, Icon } from "@chakra-ui/icons";
import { MdFileCopy } from "react-icons/md";

export const ApiKeyList = () => {
  const [apiKeys, setApiKeys] = useState<ApiKeys[]>([]);
  const [error, setError] = useState<undefined | string>();
  const [modalOpen, setModalOpen] = useState(false);
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
      await createApiKey(keyName);
      setKeyName("");
      setApiKeys(await getApiKeys());
      setModalOpen(false);
    } catch (error) {
      setError("There was an error creating your API key.");
    }
  };

  const handleDeleteApiKey = async (apiKeyId: ApiKeys["id"]) => {
    try {
      await deleteApiKey(apiKeyId);
    } catch (error) {
      console.error(error)
    }
  }

  if (error) {
    return <div>{error}</div>;
  }

  return (
    <div className="flex h-[40rem] md:h-[45rem]">
      <div className="flex w-full">
        <div className="flex w-3/4 flex-col">
          {apiKeys.map((key, i) => (
            <div
              key={key.id}
              className="my-2 flex w-full justify-between rounded border border-gray-lightgray p-4 items-center bg-white hover:bg-gray-50"
            >
              <div className="font-semibold">
                <p>{key.name}</p>
              </div>
              <div className="text-purple-softpurple">
                <p>{key.id.substring(0, 30)}...<span><Icon className="ml-1" as={MdFileCopy} color="#757087" /></span></p>
              </div>
              <div className="bg-gray-lightgray rounded-full px-3 py-1">
                <p>Connected</p>
              </div>
              <button 
                className="border border-gray-lightgray rounded-md px-3 pt-1 pb-2 shadow-sm shadow-gray-100 bg-white" 
                onClick={async () => await handleDeleteApiKey(key.id)}
              >
                <DeleteIcon color="#757087" />
              </button>
            </div>
          ))}
        </div>
        <div className="flex w-1/4 flex-col p-4 ml-2">
          <div className="text-purple-softpurple mb-3">
            <p>Communicate between applications by connecting a key to request service from the community/organization.</p>
          </div>
          <button
            data-testid="open-api-key-modal"
            className="rounded bg-purple-softpurple py-2 px-4 text-white"
            onClick={() => setModalOpen(true)}
          >
            <span className="mr-2 text-lg">+</span>Create a key
          </button>
        </div>
      </div>
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
            {error && <div>{error}</div>}
          </div>
        </div>
      </ModalTemplate>
    </div>
  );
};
