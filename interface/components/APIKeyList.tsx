// --- React components/methods
import React, { useEffect, useState } from "react";
import { createApiKey, getApiKeys } from "../utils/account-requests";

export const ApiKeyList = () => {
  const [apiKeys, setApiKeys] = useState<string[]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    let keysFetched = false;
    const fetchApiKeys = async () => {
      if (keysFetched === false) {
        try {
          const apiKeys = await getApiKeys();
          keysFetched = true;
          setApiKeys(apiKeys);
        } catch (error) {
          console.error(error);
          setError(true);
        }
      }
    };
    fetchApiKeys();
  }, []);

  if (error) {
    return <div>There was an error fetching your API keys.</div>;
  }

  return (
    <div className="flex h-[40rem] md:h-[45rem]">
      <div className="flex w-full">
        <div className="flex w-3/4 flex-col">
          {apiKeys.map((key, i) => (
            <div
              key={key}
              className="my-2 flex w-full justify-between rounded border border-gray-lightgray p-4"
            >
              <p>API Key #{i + 1}</p>
              <p>{key.substring(0, 30)}...</p>
            </div>
          ))}
        </div>
        <div className="flex w-1/4 flex-col">
          <button
            data-testid="create-button"
            className="text-md mt-5 rounded-sm border border-gray-lightgray py-1 px-6 font-librefranklin text-blue-darkblue transition delay-100 duration-150 ease-in-out hover:bg-gray-200"
            onClick={createApiKey}
          >
            <span className="text-lg">+</span>Create a key
          </button>
        </div>
      </div>
    </div>
  );
};
