import React from "react";

import {
  PAGE_PADDING,
  CONTENT_MAX_WIDTH_INCLUDING_PADDING,
} from "./PageLayout";

const PageWidthGrid = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => (
  <div
    className={`col-span-12 grid w-full grid-cols-4 gap-4 justify-self-center md:grid-cols-6 md:gap-6 lg:grid-cols-8 xl:grid-cols-12 md:mb-24 mb-40  ${className} ${PAGE_PADDING} ${CONTENT_MAX_WIDTH_INCLUDING_PADDING}`}
  >
    {children}
  </div>
);

export default PageWidthGrid;
