import React from "react";
import {
  Popover,
  PopoverArrow,
  PopoverBody,
  PopoverCloseButton,
  PopoverContent,
  PopoverTrigger,
  Portal,
} from "@chakra-ui/react";
import { InformationCircleIcon } from "@heroicons/react/24/solid";

const PopoverInfo = ({ children }: { children: React.ReactNode }) => {
  return (
    <Popover placement="top">
      <PopoverTrigger>
        <InformationCircleIcon className="inline w-4 cursor-pointer text-purple-softpurple" />
      </PopoverTrigger>
      <Portal>
        <PopoverContent>
          <PopoverArrow bg="#0E0333" />
          <PopoverCloseButton />
          <PopoverBody bg="#0E0333" borderRadius={4}>
            {children}
          </PopoverBody>
        </PopoverContent>
      </Portal>
    </Popover>
  );
};

export default PopoverInfo;
