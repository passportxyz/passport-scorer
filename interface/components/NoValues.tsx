// --- React components/methods
import { ClassNames } from "@emotion/react";
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
    <div className="grid h-full grid-cols-1 place-items-center">
      <div className="flex flex-col md:max-w-md">
        <div className="w-100 flex flex-col items-center">
          <div className="mb-8 w-fit rounded-full bg-white p-3 text-purple-gitcoinpurple">
            <div className="flex w-6 justify-around">{icon}</div>
          </div>
        </div>
        <div className="flex flex-col items-center text-center">
          <h2 className="text-xl text-gray-500">{title}</h2>
          <p className="mt-2">{description}</p>
          <button
            onClick={addRequest}
            className="mt-6 flex items-center rounded-md bg-purple-gitcoinpurple px-6 py-2 font-medium text-white"
          >
            <span className="mr-1 text-xl">+</span> {addActionText}
          </button>
        </div>
      </div>
    </div>
  );
};

export default NoValues;
