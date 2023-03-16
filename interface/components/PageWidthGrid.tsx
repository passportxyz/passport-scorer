import React, { useState } from "react";

import Header from "../components/Header";
import Footer from "../components/Footer";
const PageWidthGrid = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => (
  <div
    className={`col-span-12 grid max-w-screen-xl grid-cols-4 gap-4 justify-self-center sm:grid-cols-8 md:grid-cols-12 ${className} ${pagePadding}`}
  >
    {children}
  </div>
);

export const pagePadding = "px-4 sm:px-20";

export const HeaderContentFooterGrid = ({
  children,
}: {
  children: React.ReactNode;
}) => (
  <div className="grid h-full min-h-default w-full grid-cols-1 grid-rows-[auto_1fr_auto] items-center">
    {children}
  </div>
);

export const GlobalLayout = ({ children }: { children: React.ReactNode }) => (
  <div className="font-libre-franklin text-gray-400">{children}</div>
);

export const withHomePageLayout =
  (PageComponent: React.ComponentType) => (props: any) =>
    (
      <GlobalLayout>
        <div className="bg-purple-darkpurple">
          <HeaderContentFooterGrid>
            <Header mode="dark" className={pagePadding} />
            <PageWidthGrid className="mt-6">
              <PageComponent {...props} />
            </PageWidthGrid>
            <Footer className={pagePadding} />
          </HeaderContentFooterGrid>
        </div>
      </GlobalLayout>
    );

// This is the way to use generics w/ arrow functions
export const withPageLayout =
  <P,>(PageComponent: React.ComponentType<P>) =>
  (props: P) => {
    const [error, setError] = useState<string | null>(null);
    const [subheader, setSubheader] = useState<React.ReactNode>("");

    return (
      <GlobalLayout>
        <div className="bg-gray-bluegray">
          <HeaderContentFooterGrid>
            <div className={"border-b border-gray-300 bg-white " + pagePadding}>
              <Header className="mx-4 border-b border-b-gray-200 bg-white" />
              <div className="w-full bg-red-100">{error}</div>
              {subheader}
            </div>
            <PageWidthGrid className="">
              <PageComponent
                {...props}
                onUserError={setError}
                setSubheader={setSubheader}
              />
            </PageWidthGrid>
            <Footer className={pagePadding} />
          </HeaderContentFooterGrid>
        </div>
      </GlobalLayout>
    );
  };

export default PageWidthGrid;
