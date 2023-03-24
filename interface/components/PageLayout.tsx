/*
 * To use this layout for a new page, place the page within the
 * PageLayout <Route /> in index.tsx
 *
 *
 * Example:
 * const MyPage = () => {
 *
 *  return (
 *    <HeaderContentFooterGrid>
 *      <Header />
 *      <PageWidthGrid>
 *        <div>...content using grid columns...</div>
 *      </PageWidthGrid>
 *      <Footer />
 *    </HeaderContentFooterGrid>
 *  );
 * }
 *
 *
 */

import React from "react";
import { Outlet } from "react-router-dom";

export const PAGE_PADDING = "px-4 md:px-10 lg:px-20";
export const CONTENT_MAX_WIDTH_INCLUDING_PADDING = "max-w-[1440px]";

export const GlobalLayout = ({ children }: { children: React.ReactNode }) => (
  <div className="font-libre-franklin text-gray-400">{children}</div>
);

const PageLayout = () => {
  return (
    <GlobalLayout>
      <div className="bg-gray-bluegray">
        <Outlet />
      </div>
    </GlobalLayout>
  );
};

export default PageLayout;
