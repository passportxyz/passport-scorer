export type PrimaryBtnProps = {
  children: React.ReactNode;
  onClick: () => void;
  disabled: boolean;
};
export function PrimaryBtn({
  children,
  onClick,
  disabled,
}: PrimaryBtnProps): JSX.Element {
  return (
    <button
      className="mb-8 mt-auto w-full rounded-[12px] bg-black py-3 text-white font-medium hover:bg-gray-800 transition-colors md:mt-8 disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed"
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
