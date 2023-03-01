import { Icon } from "@chakra-ui/react";
import { InformationCircleIcon } from "@heroicons/react/24/solid";
import {
  ChartPieIcon,
  ScaleIcon,
  CurrencyDollarIcon,
  AdjustmentsVerticalIcon,
} from "@heroicons/react/24/outline";
import { AuthenticationStatus } from "@rainbow-me/rainbowkit";

import { useRouter } from "next/router";
import React, { useCallback, useEffect, useState } from "react";
import Header from "../../components/Header";
import { UseCaseInterface, useCases } from "../../components/UseCaseModal";

type DeduplicationType = "FIFO" | "LIFO";

interface GitcoinScoringMechanismInterface {
  icon: (classes?: string) => JSX.Element;
  title: string;
  description: string;
  badge?: string;
  disabled?: boolean;
  recommended?: boolean;
}

export const gitcoinScoringMechanisms: Array<GitcoinScoringMechanismInterface> =
  [
    {
      icon: (classes: string = ""): JSX.Element => (
        <ChartPieIcon className={classes} />
      ),
      title: "Unique Humanity",
      description:
        "Stamp data is evaluated and scored on a  0-100 scale where 100 includes collection of ALL stamps available. Setting a threshold above 20 will greatly reduce bad actors.",
      badge: "Recommended",
      recommended: true,
    },
    {
      icon: (classes: string = ""): JSX.Element => (
        <ScaleIcon className={classes} />
      ),
      title: "Unique Humanity (Binary)",
      description:
        "Stamp data is verified in a binary system, the data is aggregated, and scored relative to all other verifications.",
    },
    {
      icon: (classes: string = ""): JSX.Element => (
        <CurrencyDollarIcon className={classes} />
      ),
      title: "Cost of Forgery",
      description:
        "Stamp data is verified in a binary system, the data is aggregated, and scored relative to all other verifications.",
      badge: "Coming Soon",
      disabled: true,
    },
  ];

const NewScorer = ({
  authenticationStatus,
}: {
  authenticationStatus: AuthenticationStatus;
}) => {
  const router = useRouter();
  const [useCase, setUseCase] = useState<UseCaseInterface | undefined>(
    undefined
  );
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [deduplication, setDeduplication] = useState<DeduplicationType>("FIFO");
  const [gitcoinScoringMechanism, setGitcoinScoringMechanism] = useState<
    GitcoinScoringMechanismInterface | undefined
  >(undefined);

  useEffect(() => {
    // localStorage.setItem(
    //   "tempScorer",
    //   JSON.stringify({
    //     useCase: "Airdrop Protection",
    //     name: "Main Protocol Production",
    //     description: "Main Protocol is bringing AI and humans together.",
    //   })
    // );
    const scorer =
      JSON.parse(localStorage.getItem("tempScorer") || "null") || {};

    if (Object.keys(scorer).length === 0) {
      console.log("step 1");
      router.push("/dashboard");
    } else {
      // this block of code should happen only once
      const useCase = useCases[scorer.useCase];
      console.log("step 2");
      setUseCase(useCase);
      setName(scorer.name);
      setDescription(scorer.description);
    }
  }, []);

  return (
    <>
      <div className="text-purple-darkpurple">
        <Header authenticationStatus={authenticationStatus} className="px-5" />
        <hr className="mx-6 mt-5" />
        <div>
          <div className="mt-0 flex w-full justify-between border-b border-gray-300 p-6 pb-4">
            <div>
              <p className="text-xs text-purple-softpurple">
                Select a Scoring Mechanism
              </p>
              <p className="my-2 text-purple-gitcoinpurple">
                <Icon boxSize={19.5}>{useCase?.icon("#6F3FF5")}</Icon>{" "}
                {useCase?.title}
              </p>

              <h1 className="mt-2.5 font-miriamlibre text-2xl">{name}</h1>
              <p className="mt-2 text-purple-softpurple">{description}</p>
            </div>
            <div>
              <p className="mb-2 text-xs text-purple-softpurple">Scorer ID</p>
              <p>N/A</p>
            </div>
          </div>
          <div className="h-screen bg-gray-bluegray px-6 pt-4">
            <p className="text-purple-softpurple">
              Scoring mechanisms establish identity rules within Scorers.
              Scorers cannot be changed after creating them, but multiple
              Scorers can be created.
            </p>
            <div className="mt-6 grid grid-cols-1 md:grid-flow-col">
              <div>
                <span className="text-xs">
                  Select Deduplication{" "}
                  <InformationCircleIcon className="inline w-4 text-purple-softpurple" />
                </span>
                <div className="mt-2 w-full rounded border border-gray-lightgray bg-white p-6 text-purple-softpurple md:max-w-[302px]">
                  <p className="text-xs">
                    If duplicate Verified Credentials s are found, should
                    Passport score through the first or last one created?
                  </p>
                  <select
                    className="mt-6 w-full rounded border border-gray-lightgray px-4 py-2"
                    onChange={(e: any) => setDeduplication(e.target.value)}
                  >
                    <option value="FIFO">First in first out (default)</option>
                  </select>
                </div>
              </div>
              <div className="mt-6 md:mt-1">
                <p className="text-xs">
                  Gitcoin Scoring Mechanism{" "}
                  <InformationCircleIcon className="inline w-4 text-purple-softpurple" />
                </p>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-3 md:gap-6">
                  {gitcoinScoringMechanisms.map((mechanism, index) => (
                    <div
                      key={index}
                      onClick={() => setGitcoinScoringMechanism(mechanism)}
                      className={
                        "mt-2 w-full rounded border border-gray-lightgray bg-white p-6 md:max-w-[302px] " +
                        (!mechanism.disabled
                          ? "cursor-pointer hover:border-purple-gitcoinpurple"
                          : "cursor-not-allowed") +
                        (gitcoinScoringMechanism?.title === mechanism.title
                          ? " border-purple-gitcoinpurple"
                          : "")
                      }
                    >
                      <div className="flex items-center justify-between">
                        <div
                          className={
                            "flex h-12 w-12 items-center justify-center rounded-full " +
                            (mechanism.recommended
                              ? "bg-[#F0EBFF]"
                              : "border-2 border-gray-lightgray")
                          }
                        >
                          {mechanism.icon(
                            `w-7 ${
                              mechanism.recommended
                                ? "text-purple-gitcoinpurple"
                                : "text-purple-darkpurple"
                            }`
                          )}
                        </div>
                        {mechanism.badge && (
                          <div
                            className={
                              "rounded-xl px-2 py-1 text-xs " +
                              (mechanism.recommended
                                ? "bg-[#F0EBFF] text-purple-gitcoinpurple"
                                : "bg-gray-lightgray")
                            }
                          >
                            <span>{mechanism.badge}</span>
                          </div>
                        )}
                      </div>
                      <div>
                        <p className="mt-6 mb-2 text-sm">{mechanism.title}</p>
                        <p className="text-xs text-purple-softpurple">
                          {mechanism.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
                <hr className="my-6" />
                <div>
                  <p className="text-xs">
                    Custom Scoring Mechanisms{" "}
                    <InformationCircleIcon className="inline w-4 text-purple-softpurple" />
                  </p>
                  <div className="mt-2 w-full cursor-not-allowed rounded border border-gray-lightgray bg-white p-6 md:max-w-[302px]">
                    <div className="flex items-center justify-between">
                      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-gray-lightgray">
                        <AdjustmentsVerticalIcon className="w-7 text-purple-darkpurple" />
                      </div>
                      <div className="rounded-xl bg-gray-lightgray px-2 py-1 text-xs">
                        <span>Coming soon</span>
                      </div>
                    </div>
                    <div>
                      <p className="mt-6 mb-2 text-sm">Customize</p>
                      <p className="text-xs text-purple-softpurple">
                        Configure stamp weights for you community and define a
                        score that is truly customized to your use case (this is
                        an advanced scenario).
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default NewScorer;
