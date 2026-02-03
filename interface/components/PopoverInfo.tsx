import React from "react";
import { Popover } from "../ui/Popover";
import { InformationCircleIcon } from "@heroicons/react/24/solid";

const PopoverInfo = ({ children }: { children: React.ReactNode }) => {
  return (
    <Popover
      placement="top"
      trigger={
        <InformationCircleIcon className="inline w-4 cursor-pointer text-muted-foreground" />
      }
    >
      {children}
    </Popover>
  );
};

export default PopoverInfo;
