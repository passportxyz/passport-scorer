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
    className={
      `col-span-12 grid grid-cols-4 sm:grid-cols-8 md:grid-cols-12` +
      (className ? ` ${className}` : "")
    }
  >
    {children}
  </div>
);

export const HeaderContentFooterGrid = ({
  children,
}: {
  children: React.ReactNode;
}) => (
  <div className="grid h-full min-h-default grid-cols-1 grid-rows-[auto_1fr_auto] items-center px-4 sm:px-24">
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
            <Header mode="dark" />
            <PageWidthGrid className="container mt-6 self-stretch sm:self-auto">
              <PageComponent {...props} />
            </PageWidthGrid>
            <Footer />
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
            <div className="bg-white">
              <Header className="mx-4 border-b border-b-gray-200 bg-white pb-4 sm:mx-20" />
              <div className="w-full bg-red-100">{error}</div>
              {subheader}
            </div>
            <PageWidthGrid className="container mt-6 self-stretch sm:self-auto">
              <PageComponent
                {...props}
                onUserError={setError}
                setSubheader={setSubheader}
              />
            </PageWidthGrid>
            <Footer className="px-4 sm:px-20" />
          </HeaderContentFooterGrid>
        </div>
      </GlobalLayout>
    );
  };

export default PageWidthGrid;
