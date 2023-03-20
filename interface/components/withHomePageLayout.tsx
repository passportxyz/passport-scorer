import React, { useState, useCallback } from "react";

import Header from "./Header";
import Footer from "./Footer";
import PageWidthGrid from "./PageWidthGrid";
import {
  PAGE_PADDING,
  FOOTER_HEIGHT,
  HeaderContentFooterGrid,
  GlobalLayout,
} from "./withPageLayout";

const withHomePageLayout = (PageComponent: React.ComponentType) => {
  const WrappedComponent = (props: any) => (
    <GlobalLayout>
      <div className="bg-purple-darkpurple">
        <HeaderContentFooterGrid>
          <Header mode="dark" className={PAGE_PADDING} />
          <PageWidthGrid className="mt-6 h-full">
            <PageComponent {...props} />
          </PageWidthGrid>
          <Footer mode="dark" className={PAGE_PADDING + " " + FOOTER_HEIGHT} />
        </HeaderContentFooterGrid>
      </div>
    </GlobalLayout>
  );

  WrappedComponent.displayName = "withHomePageLayout";
  return WrappedComponent;
};

export default withHomePageLayout;
