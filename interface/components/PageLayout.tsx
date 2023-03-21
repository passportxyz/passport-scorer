/*
 * To use this layout for a new page, place the page within the
 * PageLayout <Route /> in index.tsx
 *
 * The child page component should generate the header and footer using the
 * context provided by this component. This is done by using the
 * useTopLevelPageContext hook.
 *
 * The child page should render 3 sections: header, content, and footer.
 * The content should be wrapped in a PageWidthGrid component.
 *
 * Example:
 * const MyPage = () => {
 *  const { generateHeader, generateFooter } = useTopLevelPageContext();
 *
 *  const Header = generateHeader();
 *  const Footer = generateFooter();
 *
 *  return (
 *    <>
 *      <Header />
 *      <PageWidthGrid>
 *        <div>...content using grid columns...</div>
 *      </PageWidthGrid>
 *      <Footer />
 *    </>
 *  );
 * }
 *
 *
 * generateHeader and generateFooter can also take a component as an argument.
 * For generateHeader, this component will be rendered in the subheader section
 * of the header. For generateFooter, this component will be rendered instead
 * of the default footer.
 *
 */

import React, { useCallback, useContext, useMemo } from "react";
import { Outlet, useOutletContext } from "react-router-dom";

import { UserContext } from "../context/userContext";

import Header from "./Header";
import Footer from "./Footer";
import Warning from "./Warning";

export const PAGE_PADDING = "px-4 md:px-20";
export const CONTENT_MAX_WIDTH_INCLUDING_PADDING = "max-w-[1440px]";
const CONTENT_MAX_WIDTH = "max-w-screen-xl";

export type TopLevelPageContext = {
  generateHeader: (Subheader?: React.ComponentType) => React.ComponentType;
  generateFooter: (FooterOverride?: React.ComponentType) => React.ComponentType;
};

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

// This is the way to use generics w/ arrow functions
const PageLayout = () => {
  const { userWarning, setUserWarning } = useContext(UserContext);

  const generateHeader = useCallback(
    (Subheader?: React.ComponentType) => {
      return () => (
        <div className={"border-b border-gray-300 bg-white " + PAGE_PADDING}>
          <Header className="border-b border-b-gray-200 bg-white" />
          <div className={"mx-auto w-full " + CONTENT_MAX_WIDTH}>
            {userWarning && (
              <Warning text={userWarning} onDismiss={() => setUserWarning()} />
            )}
            {Subheader && <Subheader />}
          </div>
        </div>
      );
    },
    [userWarning]
  );

  const generateFooter = useCallback((FooterOverride?: React.ComponentType) => {
    const CurrentFooter = FooterOverride || Footer;
    return () => <CurrentFooter className={PAGE_PADDING} />;
  }, []);

  const context: TopLevelPageContext = useMemo(
    () => ({
      generateHeader,
      generateFooter,
    }),
    [generateHeader, generateFooter]
  );

  return (
    <GlobalLayout>
      <div className="bg-gray-bluegray">
        <HeaderContentFooterGrid>
          <Outlet context={context} />
        </HeaderContentFooterGrid>
      </div>
    </GlobalLayout>
  );
};

export const useTopLevelPageContext = (): TopLevelPageContext => {
  return useOutletContext<TopLevelPageContext>();
};

export default PageLayout;
