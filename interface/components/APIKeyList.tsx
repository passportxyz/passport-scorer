// --- React components/methods
import React, { useEffect, useState } from "react";

// --- Components
import { Input } from "@chakra-ui/react";
import ModalTemplate from "./ModalTemplate";
import { SettingsIcon } from "@chakra-ui/icons";

// --- Utils
import { ApiKeys, createApiKey, getApiKeys } from "../utils/account-requests";
import NoValues from "./NoValues";

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
                  className="my-2 flex w-full justify-between rounded border border-gray-lightgray p-4"
                >
                  <p>{key.name}</p>
                  <p>{key.id.substring(0, 30)}...</p>
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
    </>
  );
};
