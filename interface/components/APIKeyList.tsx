// --- React components/methods
import React from "react";

const createAPIKey = async () => {
  try {
    const SCORER_BACKEND = process.env.NEXT_PUBLIC_PASSPORT_SCORER_BACKEND;
    const token = localStorage.getItem("access-token");
    const response = await fetch(`${SCORER_BACKEND}account/api-key`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        AUTHORIZATION: `Bearer ${token}`,
      },
    });
    const data = await response.json();
  } catch (error) {
    console.error(error);
  }
};

export const ApiKeyList = () => {
  return (
    <button
      data-testid="create-button"
      className="text-md mt-5 rounded-sm border border-gray-lightgray py-1 px-6 font-librefranklin text-blue-darkblue transition delay-100 duration-150 ease-in-out hover:bg-gray-200"
      onClick={createAPIKey}
    >
      <span className="text-lg">+</span>Create a key
    </button>
  );
};
