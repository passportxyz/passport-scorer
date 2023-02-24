// --- React components/methods
import React from "react";

type NoValuesProps = {
  addRequest: () => void;
  title: string;
  description: string;
  icon: JSX.Element;
};

const NoValues = ({
  addRequest,
  title,
  description,
  icon
}: NoValuesProps): JSX.Element => {
  return (
    <div className="flex h-[40rem] flex-col justify-center md:h-[45rem]">
      <div className="w-13 mx-auto mb-8 flex justify-center rounded-full border bg-white p-2 text-center text-gray-lightgray">
        {icon}
      </div>
      <div className="mx-auto flex flex-col justify-center text-center align-middle">
        <h2 className="mx-auto font-miriamlibre text-xl text-purple-softpurple">
          {title}
        </h2>
        <p className="mx-auto mt-2 w-9/12 font-librefranklin text-purple-softpurple">
          {description}
        </p>
        <button
          data-testid="no-values-add"
          onClick={addRequest}
          className="mx-auto mt-6 w-40 rounded-md bg-purple-softpurple pt-1 pb-2 text-white"
        >
          <span className="text-xl">+</span> Add
        </button>
      </div>
    </div>
  );
};

export default NoValues;
