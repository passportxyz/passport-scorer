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
      className="mb-8 mt-auto w-full rounded-md bg-purple-gitcoinpurple py-3 text-white md:mt-8"
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
