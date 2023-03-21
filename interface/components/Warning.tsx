import { ExclamationCircleIcon } from "@heroicons/react/24/outline";

export default function Warning({
  text,
  onDismiss,
  className,
}: {
  text: string;
  onDismiss: () => void;
  className?: string;
}) {
  return (
    <div
      className={`flex w-full items-center justify-center py-2 text-purple-darkpurple ${className}`}
    >
      <ExclamationCircleIcon height={25} color={"#D44D6E"} className="mr-4" />{" "}
      {text}{" "}
      <button onClick={onDismiss} className="ml-2 underline">
        Dismiss
      </button>
    </div>
  );
}
