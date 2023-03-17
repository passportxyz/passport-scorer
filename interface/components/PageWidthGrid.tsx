import React, { useState } from "react";

import Header from "../components/Header";
import Footer from "../components/Footer";

export const pagePadding = "px-4 md:px-20";

const contentMaxWidth = "max-w-screen-xl";
const contentMaxWidthIncludingPadding = "max-w-[1440px]";

const PageWidthGrid = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => (
  <div
    className={`col-span-12 grid w-full grid-cols-4 gap-4 justify-self-center md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-12 ${className} ${pagePadding} ${contentMaxWidthIncludingPadding}`}
  >
    {children}
  </div>
);

export const HeaderContentFooterGrid = ({
  children,
}: {
  children: React.ReactNode;
}) => (
  <div className="grid h-full min-h-default w-full grid-cols-1 grid-rows-[auto_1fr_auto]">
    {children}
  </div>
);

export const GlobalLayout = ({ children }: { children: React.ReactNode }) => (
  <div className="font-libre-franklin text-gray-400">{children}</div>
);

export const withHomePageLayout = (PageComponent: React.ComponentType) => {
  const WrappedComponent = (props: any) => (
    <GlobalLayout>
      <div className="bg-purple-darkpurple">
        <HeaderContentFooterGrid>
          <Header mode="dark" className={pagePadding} />
          <PageWidthGrid className="mt-6 h-full">
            <PageComponent {...props} />
          </PageWidthGrid>
          <Footer mode="dark" className={pagePadding} />
        </HeaderContentFooterGrid>
      </div>
    </GlobalLayout>
  );

  WrappedComponent.displayName = "withHomePageLayout";
  return WrappedComponent;
};

// This is the way to use generics w/ arrow functions
export const withPageLayout = <P,>(PageComponent: React.ComponentType<P>) => {
  const WrappedComponent = (props: P) => {
    const [error, setError] = useState<string | null>(null);
    const [subheader, setSubheader] = useState<React.ReactNode>("");

    return (
      <GlobalLayout>
        <div className="bg-gray-bluegray">
          <HeaderContentFooterGrid>
            <div className={"border-b border-gray-300 bg-white " + pagePadding}>
              <Header className="border-b border-b-gray-200 bg-white" />
              <div className={"mx-auto w-full " + contentMaxWidth}>
                <div className="w-full bg-red-100">{error}</div>
                {subheader}
              </div>
            </div>
            <PageWidthGrid className="mt-4 h-fit">
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
  WrappedComponent.displayName = "withPageLayout";
  return WrappedComponent;
};

export default PageWidthGrid;
