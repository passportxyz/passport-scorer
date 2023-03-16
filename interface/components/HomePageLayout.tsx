import React, { useState, useCallback } from "react";
import { Outlet } from "react-router-dom";

import Header from "./Header";
import Footer from "./Footer";
import PageWidthGrid from "./PageWidthGrid";
import {
  PAGE_PADDING,
  HeaderContentFooterGrid,
  GlobalLayout,
} from "./PageLayout";

const HomePageLayout = (): JSX.Element => (
  <GlobalLayout>
    <div className="bg-purple-darkpurple">
      <HeaderContentFooterGrid>
        <Header mode="dark" className={PAGE_PADDING} />
        <PageWidthGrid className="mt-6 h-full">
          <Outlet />
        </PageWidthGrid>
        <Footer mode="dark" className={PAGE_PADDING} />
      </HeaderContentFooterGrid>
    </div>
  </GlobalLayout>
);

export default HomePageLayout;
