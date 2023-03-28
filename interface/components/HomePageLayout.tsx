import React from "react";
import { Outlet } from "react-router-dom";

import MinimalHeader from "./MinimalHeader";
import Footer from "./Footer";
import PageWidthGrid from "./PageWidthGrid";
import { PAGE_PADDING, GlobalLayout } from "./PageLayout";
import HeaderContentFooterGrid from "./HeaderContentFooterGrid";

const HomePageLayout = (): JSX.Element => (
  <GlobalLayout>
    <div className="bg-purple-darkpurple">
      <HeaderContentFooterGrid>
        <MinimalHeader mode="dark" className={PAGE_PADDING} />
        <PageWidthGrid className="mt-6 h-full">
          <Outlet />
        </PageWidthGrid>
        <Footer mode="dark" />
      </HeaderContentFooterGrid>
    </div>
  </GlobalLayout>
);

export default HomePageLayout;
