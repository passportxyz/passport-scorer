// --- React components/methods
import { PlusIcon } from "@heroicons/react/24/solid";
import React from "react";

type NoValuesProps = {
  addRequest: () => void;
  title: string;
  description: string;
  icon: JSX.Element;
  addActionText: React.ReactNode;
};

const NoValues = ({
  addRequest,
  title,
  description,
  icon,
  addActionText,
}: NoValuesProps): JSX.Element => {
  return (
    <div className="grid h-full grid-cols-1 place-items-center py-6">
      <div className="flex flex-col md:max-w-md">
        <div className="w-100 flex flex-col items-center">
          <div className="mb-6 w-fit rounded-full bg-gray-100 p-4 text-gray-600">
            <div className="flex w-6 justify-around">{icon}</div>
          </div>
        </div>
        <div className="flex flex-col items-center text-center">
          <h2 className="text-xl text-gray-900 font-semibold">{title}</h2>
          <p className="mt-2 text-gray-500">{description}</p>
          <button
            data-testid="no-values-add"
            onClick={addRequest}
            className="mt-6 flex max-w-[120px] items-center rounded-[12px] bg-black px-4 py-2 font-medium text-white hover:bg-gray-800 transition-colors"
          >
            <PlusIcon className="mr-1.5 inline w-5" /> {addActionText}
          </button>
        </div>
      </div>
    </div>
  );
};

export default NoValues;
