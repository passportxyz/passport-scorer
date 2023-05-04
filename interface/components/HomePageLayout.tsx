import React from "react";
import { Outlet } from "react-router-dom";

import MinimalHeader from "./MinimalHeader";
import Footer from "./Footer";
import PageWidthGrid from "./PageWidthGrid";
import { PAGE_PADDING, GlobalLayout } from "./PageLayout";
import HeaderContentFooterGrid from "./HeaderContentFooterGrid";

const HomePageLayout = (): JSX.Element => (
  <GlobalLayout>
    <div className="grid bg-purple-darkpurple">
      <div className="col-start-1 row-start-1 grid grid-cols-6 grid-rows-2 items-center md:grid-rows-1">
        <div className="col-start-1 col-end-7 row-start-2 h-full w-full max-w-5xl bg-[url('/assets/scorerLanding.svg')] bg-cover bg-top bg-no-repeat md:col-start-5 md:row-start-1 md:bg-[size:700px] md:bg-left lg:col-start-4 xl:bg-[size:100%]" />
      </div>
      <div className="col-start-1 row-start-1">
        <HeaderContentFooterGrid>
          <MinimalHeader mode="dark" className={PAGE_PADDING} />
          <PageWidthGrid className="mt-6 h-full">
            <Outlet />
          </PageWidthGrid>
          <Footer mode="dark" hideLinks />
        </HeaderContentFooterGrid>
      </div>
    </div>
  </GlobalLayout>
);

export default HomePageLayout;
