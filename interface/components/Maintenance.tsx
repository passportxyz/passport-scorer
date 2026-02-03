// --- React Methods
import React from "react";
import { GlobalLayout, PAGE_PADDING } from "./PageLayout";
import HeaderContentFooterGrid from "./HeaderContentFooterGrid";
import Footer from "./Footer";
import MinimalHeader from "./MinimalHeader";
import PageWidthGrid from "./PageWidthGrid";

const Maintenance = () => {
  const mainContent = (
    <div className="bg-purple-darkpurple">
      <div className="font-miriam-libre text-white">
        <img src="/assets/gitcoinWordLogo.svg" alt="Human Logo" />
        <p className="md:text-7xl my-2 -ml-1 text-5xl">Passport Scorer</p>
      </div>
      <div>
        <p className="font-miriam-libre my-2 -ml-1 text-lg text-green-jade md:text-3xl">
          Sorry, we&#39;re down for maintenance.
        </p>
      </div>
      <div>
        Human Passport Scorer is currently down for scheduled maintenance. Please
        check back again as we will be back up shortly. For more information,
        check{" "}
        <a
          className="font-bold text-white hover:underline"
          href="https://twitter.com/humanpassport"
          target="_blank"
          rel="noopener noreferrer"
        >
          @HumanPassport
        </a>{" "}
        for updates.
      </div>
    </div>
  );

  return (
    <GlobalLayout>
      <div className="grid bg-purple-darkpurple">
        <div className="col-start-1 row-start-1 grid grid-cols-6 grid-rows-2 items-center md:grid-rows-1">
          <div className="col-start-1 col-end-7 row-start-2 h-full w-full max-w-5xl bg-[url('/assets/scorerLanding.svg')] bg-cover bg-top bg-no-repeat md:col-start-5 md:row-start-1 md:bg-[size:700px] md:bg-left lg:col-start-4 xl:bg-[size:100%]" />
        </div>
        <div className="col-start-1 row-start-1">
          <HeaderContentFooterGrid>
            <MinimalHeader mode="dark" className={PAGE_PADDING} />
            <PageWidthGrid className="mt-6 h-full">
              <div className="col-span-4 mb-14 justify-self-center md:self-center xl:col-span-6">
                {mainContent}
              </div>
              <div className="col-span-4 grid h-full grid-rows-[1fr_auto] md:hidden">
                <div></div>
              </div>
            </PageWidthGrid>
            <Footer mode="dark" hideLinks />
          </HeaderContentFooterGrid>
        </div>
      </div>
    </GlobalLayout>
  );
};

export default Maintenance;
