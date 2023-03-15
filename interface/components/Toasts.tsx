import { CheckCircleIcon, CloseIcon } from "@chakra-ui/icons";
import { useToast, UseToastOptions } from "@chakra-ui/react";

export const successToast = (
  message: string,
  toast: ReturnType<typeof useToast>
): UseToastOptions => {
  return {
    title: "Success!",
    status: "success",
    duration: 3000,
    isClosable: true,
    variant: "solid",
    position: "bottom",
    render: () => (
      <div
        style={{
          backgroundColor: "#0E0333",
          borderRadius: "4px",
          display: "flex",
          alignItems: "center",
          padding: "16px",
        }}
      >
        <CheckCircleIcon color="#02E2AC" boxSize={6} mr={4} />
        <span style={{ color: "white", fontSize: "16px" }}>{message}</span>
        <CloseIcon
          color="white"
          boxSize={3}
          ml="8"
          cursor="pointer"
          onClick={() => toast.closeAll()}
        />
      </div>
    ),
  };
};
