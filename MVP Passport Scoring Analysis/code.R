## Libraries
library(tidyverse)
library(dvmisc)
library(caret)
library(ggthemes)
library(kableExtra)
library(glmnet)
library(omnitheme)
library(GGally)
library(readxl)
library(fdm2id)

## Set a seed for the analysis
set.seed(1)

## Read in the wallets and forgeries datasets
wallets <- read_csv("data/20220923-001354_wallets.csv")
forgery <- read_excel("data/Cost of forgery.xlsx", sheet = 6) %>%
    slice(-1)

## Read in the loki and thor datasets
loki <- read_csv("data/FilterHandles_1664213590.csv") %>%
    select(handle = Handle) %>%
    mutate(class1 = "loki")
thor <- read_csv("data/FilterHandles_1664213662.csv") %>%
    select(handle = Handle) %>%
    mutate(class2 = "thor")

## Read in the stamps data
stamps <- read_csv("data/stamps_and_scores.csv")

## Cleaning routine - we create a baseline dataset with loki/thor indicators
# We grab the stamps, and create one column per stamp
clean_stamps <- stamps %>%
    select(handle, stamps) %>%
    left_join(thor) %>%
    left_join(loki) %>%
    mutate(class = ifelse(is.na(class1), class2, class1)) %>%
    select(-class1, -class2) %>%
    select(handle, class, everything()) %>%
    mutate(stamps = strsplit(stamps, ", ")) %>%
    rowwise() %>%
    mutate(stamps = list(gsub("\\[?\"(.*)\"]?", "\\1", stamps))) %>%
    unnest(stamps) %>%
    mutate(value = 1) %>%
    spread(key = stamps, value = value) %>%
    select(-`[]`)

#@ Set NAs to zero and ensure that the class column is a factor
clean_stamps[,-2][is.na(clean_stamps[,-2])] <- 0
clean_stamps$class <- factor(clean_stamps$class)

###
### Logistic Regression Model
###
my_glm <- glm(class ~ ., data = clean_stamps %>%
                  filter(!is.na(class)) %>%
                  select(-handle), family = "binomial")

# Predictions
glm_preds <- predict(my_glm, type = "response", newdata = clean_stamps)

# Coefficients
glm_co <- coef(my_glm)

###
### Regularized Logistic Regression Model
###
my_glmnet_cv <- cv.glmnet(clean_stamps %>%
                              filter(!is.na(class)) %>%
                              select(-handle, -class) %>%
                              as.matrix, clean_stamps %>%
                              filter(!is.na(class)) %>%
                              select(class) %>% .[[1]], family = "binomial", type.measure = 'class')

# Predictions
glmnet_cv_preds <- predict(my_glmnet_cv, type = "response", newx = clean_stamps %>%
                               select(-handle, -class) %>%
                               as.matrix)[,1]

# Coefficients
glmco_cv <- coef(my_glmnet_cv, s = 0.01)

###
### STUMP (Single level Tree) Model
###
stmp <- STUMP(clean_stamps %>%
                  filter(!is.na(class)) %>%
                  select(-handle, -class) %>%
                  as.matrix, clean_stamps %>%
                  filter(!is.na(class)) %>%
                  select(class) %>% .[[1]], randomvar = FALSE)

## Bind all the model results to the stamps data
clean_stamps_models <- clean_stamps %>% gather(key = Variable, value = Value, 3:ncol(.)) %>%
    left_join(
        tibble(
            Variable = forgery$Stamp,
            Kish = as.numeric(forgery$COF_Kish_Estimates)
        )
    ) %>%
    left_join(
        tibble(
            Variable = forgery$Stamp,
            Regen = as.numeric(forgery$FDD_Regen_Score_Omni)
        )
    ) %>%
    left_join(
        tibble(
            Variable = names(coef(my_glm)),
            Logistic = as.numeric(coef(my_glm))
        )
    ) %>%
    left_join(
        tibble(
            Variable = rownames(glmco_cv),
            Regularized = glmco_cv[,1]
        )
    )

# Build a table of the logistic and regularized regression
l_pred = tibble(
    handle = clean_stamps$handle,
    Logistic = glm_preds,
    Regularized = glmnet_cv_preds
)

###
### Primary Modeling Dataset
###
binded_models <- clean_stamps_models %>%
    group_by(handle, class) %>%
    summarise(
        Kish = sum(Kish * Value),
        Regen = sum(Regen * Value)
    ) %>%
    left_join(l_pred)

## Find the best decision rule for Kish and Regen
kish_stmp <- STUMP(binded_models %>% ungroup() %>% filter(!is.na(class)) %>% select(Kish) %>% as.data.frame, binded_models %>% ungroup() %>% filter(!is.na(class)) %>% .$class, randomvar = FALSE)
regen_stmp <- STUMP(binded_models %>% ungroup() %>% filter(!is.na(class)) %>% select(Regen) %>% as.data.frame, binded_models %>% ungroup() %>% filter(!is.na(class)) %>% .$class, randomvar = FALSE)

## Check the table of predictions
table(predict(kish_stmp, test = binded_models %>% ungroup() %>% filter(!is.na(class)) %>% select(Kish) %>% as.data.frame))
table(predict(regen_stmp, test = binded_models %>% ungroup() %>% filter(!is.na(class)) %>% select(Regen) %>% as.data.frame))

## Kish Score Distribution
p1 <- ggplot(data = binded_models %>%
           ungroup() %>%
           arrange(Kish) %>%
           mutate(ID = 1:nrow(.)), aes(x = ID, y = Kish)) +
    geom_point(colour = "#5C4C6F") +
    scale_y_continuous(breaks = c(0, 1, 2, 5, 10, 20, 50, 100, 200, 500,
                             1000, 2000, 5000, 10000, 20000, 50000),
                  labels = function(x) paste0("$", scales::comma(x)),
                  trans=scales::pseudo_log_trans(base = 10)) +
    scale_x_continuous(breaks = scales::pretty_breaks(n = 10)) +
    labs(
        title = "Sorted Gitcoin Passport $USD Values derived from Kiashoraditya's Research",
        subtitle = "n = 35127",
        x = "Sorted IDs",
        y = "Passport Value ($USD)"
    ) +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 40)

ggsave(p1, filename = "outputs/kish_distribution.png", width = 12, height = 8)

# Regen Score Distribution
p2 <- ggplot(data = binded_models %>%
           ungroup() %>%
           filter(Regen > 0) %>%
           arrange(Regen) %>%
           mutate(ID = 1:nrow(.)), aes(x = ID, y = Regen)) +
    geom_point(colour = "#5C4C6F") +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 20),
                       limits = c(0, NA)) +
    scale_x_continuous(breaks = scales::pretty_breaks(n = 10)) +
    labs(
        title = "Sorted Gitcoin Regen Scores for Passport Holders",
        subtitle = "n = 3360 with 0 scoring Passports removed",
        y = "Gitcoin Regen Score",
        x = "Sorted IDs"
    ) +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 40)

ggsave(p2, filename = "outputs/regen_distribution.png", width = 12, height = 8)

# Regularized Probability Scores
p3 <- ggplot(data = binded_models %>% arrange(Regularized) %>%
           ungroup() %>%
           mutate(ID = 1:nrow(.)), aes(x = ID, y = Regularized, colour = class)) +
    geom_point() +
    scale_colour_manual(values = c("#F3587D", "#27AE60")) +
    scale_x_continuous(breaks = scales::pretty_breaks(n = 10)) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 10),
                       labels = scales::percent,
                       limits = c(0, 1)) +
    labs(title = "Sorted Probability Scores",
         subtitle = "For the Regularized Logistic Regression Model",
         y = "Predicted Probability (%)",
         x = "ID") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 80)

ggsave(p3, filename = "outputs/regularized_distribution.png", width = 12, height = 8)

p4 <- ggplot(data = binded_models %>% arrange(Logistic) %>%
           ungroup() %>%
           mutate(ID = 1:nrow(.)), aes(x = ID, y = Logistic, colour = class)) +
    geom_point() +
    scale_colour_manual(values = c("#F3587D", "#27AE60")) +
    scale_x_continuous(breaks = scales::pretty_breaks(n = 10)) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 10),
                       labels = scales::percent,
                       limits = c(0, 1)) +
    labs(title = "Sorted Probability Scores",
         subtitle = "For the Logistic Regression Model",
         y = "Predicted Probability (%)",
         x = "ID") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 80)

ggsave(p4, filename = "outputs/logistic_distribution.png", width = 12, height = 8)

p51 <- binded_models %>%
    ggplot(aes(x = class, y = Kish, fill = class)) +
    geom_boxplot() +
    scale_fill_manual(values = c("#F3587D", "#27AE60")) +
    scale_y_log10(labels = scales::comma, breaks = c(1, 2, 5, 10, 20, 50, 100,
                                                     200, 500, 1000, 2000, 5000, 10000,
                                                     20000, 50000),
                  limits = c(1, NA)) +
    labs(
        title = "Distributional Comparison of Scores for the Kish Method",
        subtitle = "Comparing the Loki and Thor groups"
    )

ggsave(p51, filename = "outputs/loki_thor_compare_kish.png", width = 12, height = 8)

p52 <- binded_models %>%
    ggplot(aes(x = class, y = Regen, fill = class)) +
    geom_boxplot() +
    scale_fill_manual(values = c("#F3587D", "#27AE60")) +
    scale_y_log10(labels = scales::comma, breaks = c(1, 2, 5, 10, 20, 50, 100),
                  limits = c(1, NA)) +
    labs(
        title = "Distributional Comparison of Scores for the Regen Method",
        subtitle = "Comparing the Loki and Thor groups"
    )

ggsave(p52, filename = "outputs/loki_thor_compare_regen.png", width = 12, height = 8)

p53 <- binded_models %>%
    ggplot(aes(x = class, y = Logistic, fill = class)) +
    geom_boxplot() +
    scale_fill_manual(values = c("#F3587D", "#27AE60")) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 20)) +
    labs(
        title = "Distributional Comparison of Scores for the Logistic Regression Method",
        subtitle = "Comparing the Loki and Thor groups"
    )

ggsave(p53, filename = "outputs/loki_thor_compare_logistic.png", width = 12, height = 8)

p54 <- binded_models %>%
    ggplot(aes(x = class, y = Regularized, fill = class)) +
    geom_boxplot() +
    scale_fill_manual(values = c("#F3587D", "#27AE60")) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 20)) +
    labs(
        title = "Distributional Comparison of Scores for the Regularized Logistic Regression Method",
        subtitle = "Comparing the Loki and Thor groups"
    )

ggsave(p54, filename = "outputs/loki_thor_compare_regularized.png", width = 12, height = 8)

###
### Output Dataset
###
stamps_scoring_methods <- stamps %>%
    select(handle, stamps) %>%
    left_join(binded_models) %>%
    left_join(wallets) %>%
    left_join(
        tibble(
            handle = clean_stamps$handle,
            stamps_collected = rowSums(clean_stamps[,-c(1,2)])
        )
    ) %>%
    select(`Wallet Address` = address, `Gitcoin Handle` = handle, `Thor/Loki Indicator` = class,
           `Stamps Collected` = stamps_collected,
           `Logistic Regression Score` = Logistic, `Regularized Regression Score` = Regularized,
           `COF Kish Score` = Kish, `Gitcoin Regen Score` = Regen, Stamps = stamps)

stamps_scoring_methods %>% write_csv("outputs/stamps_scoring_methods.csv")

###
### Logistic / Regularized Model Deep-Dive
###

## Write out the model coefficients
model_coefficients <- tibble(
    Stamp = names(glm_co),
    Logistic = glm_co,
    Regularized = glmco_cv[,1]
)

write_csv(model_coefficients, "outputs/logistic_and_regularized_coefficients.csv")

## Write out all coefficients
model_coefficients %>%
    select(Stamp, Coefficient = Logistic) %>%
    write_csv("weights/scoringmethod_LogRegOmni_112322.csv")

model_coefficients %>%
    select(Stamp, Coefficient = Regularized) %>%
    write_csv("weights/scoringmethod_RegularizedLogRegOmni_112322.csv")

forgery %>%
    select(Stamp, Coefficient = COF_Kish_Estimates) %>%
    write_csv("weights/scoringmethod_CoFKish_112322.csv")

forgery %>%
    select(Stamp, Coefficient = FDD_Regen_Score_Omni) %>%
    write_csv("weights/scoringmethod_GitcoinRegenOmni_112322.csv")

## Create the model confusion matrix
model_confusion_matrix <- tibble(
    glm_pred = glm_preds,
    glmnet_cv_pred = glmnet_cv_preds,
    handle = clean_stamps$handle,
    class = clean_stamps$class
) %>%
    mutate(glm_prediction = ifelse(glm_pred >= .5, "thor", "loki"),
           glmnet_cv_prediction = ifelse(glmnet_cv_pred >= .5, "thor", "loki")) %>%
    filter(!is.na(class))

table(model_confusion_matrix$glm_prediction, model_confusion_matrix$class)
table(model_confusion_matrix$glmnet_cv_prediction, model_confusion_matrix$class)

## Get a color scale gradient
cc <- scales::seq_gradient_pal("#F3587D", "#27AE60", "Lab")(seq(0,1,length.out=20))

## Pyramid Plot of Coefficients
p61 <- tibble(coef = names(glm_co), s1 = glm_co) %>%
    filter(!is.na(s1)) %>%
    arrange(desc(s1)) %>%
    mutate(coef = factor(coef, levels = rev(coef))) %>%
    mutate(cval = ifelse(s1 > 0, "Positive", "Negative")) %>%
    ggplot(aes(x = s1, y = coef, fill = cval)) +
    geom_bar(stat = "identity") +
    scale_fill_manual(values = c("#F3587D", "#27AE60")) +
    scale_x_continuous(labels = function(x) x, breaks = scales::pretty_breaks(n = 15)) +
    theme_grey() +
    watermark_img("images/gc.png", location = "br", alpha = 0.8, width = 60) +
    labs(
        title = "Coefficient for each Stamp in the Logistic Regression Model",
        subtitle = "Positive Coefficients = More Likely to be Thor",
        x = "Coefficient Value",
        y = "Coefficient",
        fill = "Direction"
    )

ggsave(p61, filename = "outputs/pyramid_plot_logistic.png", width = 12, height = 8)

p62 <- tibble(coef = rownames(glmco_cv), s1 = glmco_cv[,1]) %>%
    filter(!is.na(s1)) %>%
    arrange(desc(s1)) %>%
    mutate(coef = factor(coef, levels = rev(coef))) %>%
    mutate(cval = ifelse(s1 > 0, "Positive", "Negative")) %>%
    ggplot(aes(x = s1, y = coef, fill = cval)) +
    geom_bar(stat = "identity") +
    scale_fill_manual(values = c("#F3587D", "#27AE60")) +
    scale_x_continuous(labels = function(x) x, breaks = scales::pretty_breaks(n = 15)) +
    theme_grey() +
    watermark_img("images/gc.png", location = "br", alpha = 0.8, width = 60) +
    labs(
        title = "Coefficient for each Stamp in the Regularized Logistic Regression Model",
        subtitle = "Positive Coefficients = More Likely to be Thor",
        x = "Coefficient Value",
        y = "Coefficient",
        fill = "Direction"
    )

ggsave(p62, filename = "outputs/pyramid_plot_regularized.png", width = 12, height = 8)

###
### Coefficient Interpretation
###

# i. ENS Coefficient for Logistic = 0.8042. ENS Odds Ratio: e^(0.8042) = 2.23
# A Gitcoin Passport having the ENS stamp is 2.23x more likely to be Thor.

# ii. LinkedIn Coefficient for Logistic = 1.2076. Linkedin Odds Ratio: e^(1.2076) = 3.35
# A Gitcoin Passport having the Linkedin stamp is 3.35x more likely to be Thor.

# iii. CommunityStakingGold Coefficient for Logistic = 2.7197. CommunityStakingGold Odds Ratio: e^(2.7197) = 15.18
# A Gitcoin Passport having the CommunityStakingGold stamp is 15.18x more likely to be Thor.

# iv. BrightId Coefficient for Logistic = -0.3741. BrightId Odds Ratio: e^(-0.3741) = 0.69
# A Gitcoin Passport having the BrightId stamp is 0.69x more likely to be Thor, or equivalently, 1.45x more likely to be Loki

# v. SelfStakingGold Coefficient for Logistic = -1.7071. SelfStakingGold Odds Ratio: e^(-1.7071) = 0.18
# A Gitcoin Passport having the SelfStakingGold stamp is 0.18x more likely to be Thor, or equivalently, 5.56x more likely to be Loki

# vi. SelfStakingSilver Coefficient for Logistic = -14.0829. SelfStakingSilver Odds Ratio: e^(-14.0829) = 0.0000008
# A Gitcoin Passport having the SelfStakingSilver stamp is 0.0000008x more likely to be Thor, or equivalently, 1,250,000x more likely to be Loki

# Summary statistics of the predicted probabilities of logistic/ regularized
summary(binded_models %>% filter(!is.na(class)) %>% .$Logistic)
summary(binded_models %>% filter(!is.na(class)) %>% .$Regularized)

# Predicted Probabilities
p71 <- binded_models %>%
    ungroup() %>%
    filter(!is.na(class)) %>%
    mutate(Prediction_Col = cut(Logistic, breaks = c(seq(0, 1, by = .05), Inf),
                                labels = sapply(seq(0, 1, by = .05), function(x) {
                                    paste0(scales::percent(x), "-", scales::percent(x + .05))
                                }))) %>%
    ggplot(aes(x = Prediction_Col, fill = Prediction_Col)) +
    geom_bar(colour = "black") +
    scale_fill_manual(values = cc) +
    scale_x_discrete() +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 10)) +
    labs(title = "Predicted Probability of Thor",
         subtitle = "For the Logistic Regression Model",
         x = "Predicted Probability (%)",
         y = "Count") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 60) +
    theme(legend.position = "off")

ggsave(p71, filename = "outputs/predicted_probabilities_logistic.png", width = 12, height = 8)

p72 <- binded_models %>%
    ungroup() %>%
    filter(!is.na(class)) %>%
    mutate(Prediction_Col = cut(Regularized, breaks = c(seq(0, 1, by = .05), Inf),
                                labels = sapply(seq(0, 1, by = .05), function(x) {
                                    paste0(scales::percent(x), "-", scales::percent(x + .05))
                                }))) %>%
    ggplot(aes(x = Prediction_Col, fill = Prediction_Col)) +
    geom_bar(colour = "black") +
    scale_fill_manual(values = cc) +
    scale_x_discrete() +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 10)) +
    labs(title = "Predicted Probability of Thor",
         subtitle = "For the Regularized Logistic Regression Model",
         x = "Predicted Probability (%)",
         y = "Count") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tr", alpha = 0.8, width = 60) +
    theme(legend.position = "off")

ggsave(p72, filename = "outputs/predicted_probabilities_regularized.png", width = 12, height = 8)

# c.	Pseudo logged dotplot of the predicted probabilities of both methods

p81 <- ggplot(data = binded_models %>% arrange(Logistic) %>%
           ungroup() %>%
           filter(!is.na(class)) %>%
           mutate(ID = 1:nrow(.)), aes(x = ID, y = Logistic, colour = class)) +
    geom_point() +
    scale_x_continuous(breaks = scales::pretty_breaks(n = 20)) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 20),
                       labels = scales::percent,
                       limits = c(0, 1)) +
    scale_colour_manual(values = c("#F3587D", "#27AE60")) +
    labs(title = "Sorted Probability Scores",
         subtitle = "For the Logistic Regression Model",
         y = "Predicted Probability (%)",
         x = "ID") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 80)

ggsave(p81, filename = "outputs/sorted_probabilities_logistic.png", width = 12, height = 8)


p82 <- ggplot(data = binded_models %>% arrange(Regularized) %>%
           ungroup() %>%
           filter(!is.na(class)) %>%
           mutate(ID = 1:nrow(.)), aes(x = ID, y = Regularized, colour = class)) +
    geom_point() +
    scale_colour_manual(values = c("#F3587D", "#27AE60")) +
    scale_x_continuous(breaks = scales::pretty_breaks(n = 20)) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 20),
                       labels = scales::percent,
                       limits = c(0, 1)) +
    labs(title = "Sorted Probability Scores",
         subtitle = "For the Regularized Logistic Regression Model",
         y = "Predicted Probability (%)",
         x = "ID") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 80)

ggsave(p82, filename = "outputs/sorted_probabilities_regularized.png", width = 12, height = 8)


# d.	logged dotplot of the predicted probabilities of both methods (0’s removed)
p821 <- ggplot(data = binded_models %>% filter(Kish > 0) %>% arrange(Logistic) %>%
           ungroup() %>%
           filter(!is.na(class)) %>%
           mutate(ID = 1:nrow(.)), aes(x = ID, y = Logistic, colour = class)) +
    geom_point() +
    scale_colour_manual(values = c("#F3587D", "#27AE60")) +
    scale_x_continuous(breaks = scales::pretty_breaks(n = 20)) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 20),
                       labels = scales::percent,
                       limits = c(0, 1)) +
    labs(title = "Sorted Probability Scores (Zeroes Removed)",
         subtitle = "For the Logistic Regression Model",
         y = "Predicted Probability (%)",
         x = "ID") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 80)

ggsave(p821, filename = "outputs/sorted_probabilities_logistic_nozeroes.png", width = 12, height = 8)


p822 <-ggplot(data = binded_models %>% filter(Kish > 0) %>% arrange(Regularized) %>%
           ungroup() %>%
           filter(!is.na(class)) %>%
           mutate(ID = 1:nrow(.)), aes(x = ID, y = Regularized, colour = class)) +
    geom_point() +
    scale_colour_manual(values = c("#F3587D", "#27AE60")) +
    scale_x_continuous(breaks = scales::pretty_breaks(n = 20)) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 20),
                       labels = scales::percent,
                       limits = c(0, 1)) +
    labs(title = "Sorted Probability Scores (Zeroes Removed)",
         subtitle = "For the Regularized Logistic Regression Model",
         y = "Predicted Probability (%)",
         x = "ID") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 80)

ggsave(p822, filename = "outputs/sorted_probabilities_regularized_nozeroes.png", width = 12, height = 8)

# e.	Boxplot of the predicted probabilities for the thor vs loki sets across both methods

p83 <- binded_models %>%
    filter(!is.na(class)) %>%
    ggplot(aes(x = class, y = Logistic, fill = class)) +
    geom_boxplot() +
    scale_fill_manual(values = c("#F3587D", "#27AE60")) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 20)) +
    labs(
        title = "Distributional Comparison of Scores for the Logistic Regression Method",
        subtitle = "Comparing the Loki and Thor groups"
    )

ggsave(p83, filename = "outputs/score_distributions_logistic.png", width = 12, height = 8)


p84 <- binded_models %>%
    filter(!is.na(class)) %>%
    ggplot(aes(x = class, y = Regularized, fill = class)) +
    geom_boxplot() +
    scale_fill_manual(values = c("#F3587D", "#27AE60")) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 20)) +
    labs(
        title = "Distributional Comparison of Scores for the Regularized Logistic Regression Method",
        subtitle = "Comparing the Loki and Thor groups"
    )

ggsave(p84, filename = "outputs/score_distributions_regularized.png", width = 12, height = 8)

# f.	Boxplot of the predicted probabilities for the thor vs loki sets across both methods
# with 0’s removed

p831 <- binded_models %>%
    filter(!is.na(class),
           Kish > 0) %>%
    ggplot(aes(x = class, y = Logistic, fill = class)) +
    geom_boxplot() +
    scale_fill_manual(values = c("#F3587D", "#27AE60")) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 20)) +
    labs(
        title = "Distributional Comparison of Scores for the Logistic Regression Method (zeroes removed)",
        subtitle = "Comparing the Loki and Thor groups"
    )

ggsave(p831, filename = "outputs/score_distributions_logistic_nozeroes.png", width = 12, height = 8)


p841 <- binded_models %>%
    filter(!is.na(class),
           Kish > 0) %>%
    ggplot(aes(x = class, y = Regularized, fill = class)) +
    geom_boxplot() +
    scale_fill_manual(values = c("#F3587D", "#27AE60")) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 20)) +
    labs(
        title = "Distributional Comparison of Scores for the Regularized Logistic Regression Method (zeroes removed)",
        subtitle = "Comparing the Loki and Thor groups"
    )

ggsave(p841, filename = "outputs/score_distributions_regularized_nozeroes.png", width = 12, height = 8)

binded_models %>%
    filter(!is.na(class)) %>%
    group_by(class) %>%
    summarise(
        Logistic = mean(Logistic),
        Regularized = mean(Regularized)
    )

###
### Kish / Regen Deep-Dive
###

p63 <- tibble(coef = forgery$Stamp, s1 = as.numeric(forgery$COF_Kish_Estimates)) %>%
    filter(!is.na(s1)) %>%
    arrange(desc(s1)) %>%
    mutate(coef = factor(coef, levels = rev(coef))) %>%
    mutate(cval = ifelse(s1 > 0, "Positive", "Negative")) %>%
    ggplot(aes(x = s1, y = coef, fill = cval)) +
    geom_bar(stat = "identity") +
    scale_fill_manual(values = c("#F3587D", "#27AE60")) +
    scale_x_continuous(labels = function(x) x, breaks = scales::pretty_breaks(n = 15)) +
    theme_grey() +
    watermark_img("images/gc.png", location = "br", alpha = 0.8, width = 60) +
    labs(
        title = "Coefficient for each Stamp in the Kish Model",
        subtitle = "Positive Coefficients = More Likely to be Thor",
        x = "Coefficient Value",
        y = "Coefficient",
        fill = "Direction"
    )

ggsave(p63, filename = "outputs/pyramid_plot_kish.png", width = 12, height = 8)

p64 <- tibble(coef = forgery$Stamp, s1 = as.numeric(forgery$FDD_Regen_Score_Omni)) %>%
    filter(!is.na(s1)) %>%
    arrange(desc(s1)) %>%
    mutate(coef = factor(coef, levels = rev(coef))) %>%
    mutate(cval = ifelse(s1 > 0, "Positive", "Negative")) %>%
    ggplot(aes(x = s1, y = coef, fill = cval)) +
    geom_bar(stat = "identity") +
    scale_fill_manual(values = c("#F3587D", "#27AE60")) +
    scale_x_continuous(labels = function(x) x, breaks = scales::pretty_breaks(n = 15)) +
    theme_grey() +
    watermark_img("images/gc.png", location = "br", alpha = 0.8, width = 60) +
    labs(
        title = "Coefficient for each Stamp in the Regen Model",
        subtitle = "Positive Coefficients = More Likely to be Thor",
        x = "Coefficient Value",
        y = "Coefficient",
        fill = "Direction"
    )

ggsave(p64, filename = "outputs/pyramid_plot_regen.png", width = 12, height = 8)

# Summary statistics of the predicted probabilities of both methods
summary(binded_models %>% filter(!is.na(class)) %>% .$Kish)
summary(binded_models %>% filter(!is.na(class)) %>% .$Regen)

p93 <- binded_models %>%
    filter(Kish > 0, !is.na(class)) %>%
    ggplot(aes(x = Kish)) +
    geom_histogram(colour = "black") +
    scale_x_log10(breaks = c(1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000),
                  labels = scales::dollar) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 10)) +
    labs(title = "Distribution of Kish Scores for Handles",
         subtitle = "Zero-stamp Passports Removed",
         x = "Kish Score ($)",
         y = "Count") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tr", alpha = 0.8, width = 60) +
    theme(legend.position = "off")

ggsave(p93, filename = "outputs/predicted_scores_kish.png", width = 12, height = 8)

p94 <- binded_models %>%
    filter(Regen > 0, !is.na(class)) %>%
    ggplot(aes(x = Regen)) +
    geom_histogram(colour = "black") +
    scale_x_log10(breaks = c(1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000),
                  labels = scales::comma) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 10)) +
    labs(title = "Distribution of Regen Scores for Handles",
         subtitle = "Zero-stamp Passports Removed",
         x = "Regen Score",
         y = "Count") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tr", alpha = 0.8, width = 60) +
    theme(legend.position = "off")

ggsave(p94, filename = "outputs/predicted_scores_regen.png", width = 12, height = 8)

p95 <- ggplot(data = binded_models %>% arrange(Kish) %>%
           ungroup() %>%
           filter(!is.na(class)) %>%
           mutate(ID = 1:nrow(.)), aes(x = ID, y = Kish, colour = class)) +
    geom_point() +
    scale_colour_manual(values = c("#F3587D", "#27AE60")) +
    scale_x_continuous(breaks = scales::pretty_breaks(n = 20)) +
    scale_y_continuous(breaks = c(0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000),
                      trans=scales::pseudo_log_trans(base = 10),
                      limits = c(0, NA)) +
    labs(title = "Sorted USD($) Kish Scores",
         subtitle = "Based on Kiashoraditya's Research",
         y = "Score ($)",
         x = "ID") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 60)

ggsave(p95, filename = "outputs/sorted_scores_kish.png", width = 12, height = 8)

p96 <- ggplot(data = binded_models %>% arrange(Regen) %>%
           ungroup() %>%
           filter(!is.na(class)) %>%
           mutate(ID = 1:nrow(.)), aes(x = ID, y = Regen, colour = class)) +
    geom_point() +
    scale_colour_manual(values = c("#F3587D", "#27AE60")) +
    scale_x_continuous(breaks = scales::pretty_breaks(n = 20)) +
    scale_y_continuous(breaks = c(0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000),
                       trans=scales::pseudo_log_trans(base = 10),
                       limits = c(0, NA)) +
    labs(title = "Sorted Regen Scores",
         y = "Score",
         x = "ID") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 60)

ggsave(p96, filename = "outputs/sorted_scores_regen.png", width = 12, height = 8)

p951 <- ggplot(data = binded_models %>% arrange(Kish) %>%
           ungroup() %>%
           filter(!is.na(class),
                  Kish > 0) %>%
           mutate(ID = 1:nrow(.)), aes(x = ID, y = Kish, colour = class)) +
    geom_point() +
    scale_colour_manual(values = c("#F3587D", "#27AE60")) +
    scale_x_continuous(breaks = scales::pretty_breaks(n = 20)) +
    scale_y_log10(breaks = c(1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000)) +
    labs(title = "Sorted USD($) Kish Scores (zeroes removed)",
         subtitle = "Based on Kiashoraditya's Research",
         y = "Score ($)",
         x = "ID") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 60)

ggsave(p951, filename = "outputs/sorted_scores_kish_nozeroes.png", width = 12, height = 8)

p952 <- ggplot(data = binded_models %>% arrange(Regen) %>%
           ungroup() %>%
           filter(!is.na(class),
                  Regen > 0) %>%
           mutate(ID = 1:nrow(.)), aes(x = ID, y = Regen, colour = class)) +
    geom_point() +
    scale_colour_manual(values = c("#F3587D", "#27AE60")) +
    scale_x_continuous(breaks = scales::pretty_breaks(n = 20)) +
    scale_y_log10(breaks = c(1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000)) +
    labs(title = "Sorted Regen Scores (zeroes removed)",
         y = "Score",
         x = "ID") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 60)

ggsave(p952, filename = "outputs/sorted_scores_regen_nozeroes.png", width = 12, height = 8)

p97 <- binded_models %>%
    filter(!is.na(class)) %>%
    ggplot(aes(x = class, y = Kish, fill = class)) +
    geom_boxplot() +
    scale_fill_manual(values = c("#F3587D", "#27AE60")) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 20)) +
    labs(
        title = "Distributional Comparison of Scores for Kish's Method",
        subtitle = "Comparing the Loki and Thor groups"
    )

ggsave(p97, filename = "outputs/score_distributions_kish.png", width = 12, height = 8)

p98 <- binded_models %>%
    filter(!is.na(class)) %>%
    ggplot(aes(x = class, y = Regen, fill = class)) +
    geom_boxplot() +
    scale_fill_manual(values = c("#F3587D", "#27AE60")) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 20)) +
    labs(
        title = "Distributional Comparison of Scores for Regen",
        subtitle = "Comparing the Loki and Thor groups"
    )

ggsave(p97, filename = "outputs/score_distributions_regen.png", width = 12, height = 8)

p971 <- binded_models %>%
    filter(!is.na(class), Kish > 0) %>%
    ggplot(aes(x = class, y = Kish, fill = class)) +
    geom_boxplot() +
    scale_fill_manual(values = c("#F3587D", "#27AE60")) +
    scale_y_log10(breaks = c(1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000),
                  labels = scales::dollar) +
    labs(
        title = "Distributional Comparison of Scores for Kish's Method (zeroes removed)",
        subtitle = "Comparing the Loki and Thor groups",
        y = "Score ($)"
    )

ggsave(p971, filename = "outputs/score_distributions_kish_nozeroes.png", width = 12, height = 8)

p981 <- binded_models %>%
    filter(!is.na(class), Regen > 0) %>%
    ggplot(aes(x = class, y = Regen, fill = class)) +
    geom_boxplot() +
    scale_fill_manual(values = c("#F3587D", "#27AE60")) +
    scale_y_log10(breaks = c(1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000)) +
    labs(
        title = "Distributional Comparison of Scores for Regen (zeroes removed)",
        subtitle = "Comparing the Loki and Thor groups"
    )

ggsave(p981, filename = "outputs/score_distributions_regen_nozeroes.png", width = 12, height = 8)

binded_models %>%
    filter(!is.na(class)) %>%
    group_by(class) %>%
    summarise(
        Kish = mean(Kish),
        Regen = mean(Regen)
    )

###
### Result Comparison
###

p100 <- binded_models %>%
    ungroup() %>%
    mutate(Prediction_Col = cut(Logistic, breaks = c(seq(0, 1, by = .05), Inf),
                                labels = sapply(seq(0, 1, by = .05), function(x) {
                                    paste0(scales::percent(x), "-", scales::percent(x + .05))
                                }))) %>%
    ggplot(aes(x = Prediction_Col, fill = Prediction_Col)) +
    geom_bar(colour = "black") +
    scale_fill_manual(values = cc) +
    scale_x_discrete() +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 10)) +
    labs(title = "Distribution of Predicted Probabilities of being non-Sybil (Thor) using Logistic Regression",
         subtitle = "Scored on All Passports",
         x = "Predicted Probability (%)",
         y = "Count") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tr", alpha = 0.8, width = 60) +
    theme(legend.position = "off")

ggsave(p100, filename = "outputs/non_sybil_probability_logistic.png", width = 12, height = 8)

p101 <- binded_models %>%
    ungroup() %>%
    mutate(Prediction_Col = cut(Regularized, breaks = c(seq(0, 1, by = .05), Inf),
                                labels = sapply(seq(0, 1, by = .05), function(x) {
                                    paste0(scales::percent(x), "-", scales::percent(x + .05))
                                }))) %>%
    ggplot(aes(x = Prediction_Col, fill = Prediction_Col)) +
    geom_bar(colour = "black") +
    scale_fill_manual(values = cc) +
    scale_x_discrete() +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 10)) +
    labs(title = "Distribution of Predicted Probabilities of being non-Sybil (Thor) using Regularized Logistic Regression",
         subtitle = "Scored on All Passports",
         x = "Predicted Probability (%)",
         y = "Count") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tr", alpha = 0.8, width = 60) +
    theme(legend.position = "off")

ggsave(p101, filename = "outputs/non_sybil_probability_regularized.png", width = 12, height = 8)

p102 <- binded_models %>%
    ungroup() %>%
    filter(Kish > 0) %>%
    ggplot(aes(x = Kish)) +
    geom_histogram(colour = "black") +
    scale_x_log10(breaks = c(1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000),
                  labels = scales::dollar) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 10)) +
    labs(title = "Distribution of Kish Scores for All Passports",
         subtitle = "Zero-stamp Passports Removed",
         x = "Kish Score ($)",
         y = "Count") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tr", alpha = 0.8, width = 60) +
    theme(legend.position = "off")

ggsave(p102, filename = "outputs/non_sybil_score_kish.png", width = 12, height = 8)

p103 <- binded_models %>%
    filter(Regen > 0, !is.na(class)) %>%
    ggplot(aes(x = Regen)) +
    geom_histogram(colour = "black") +
    scale_x_log10(breaks = c(1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000),
                  labels = scales::comma) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 10)) +
    labs(title = "Distribution of Regen Scores for All Passports",
         subtitle = "Zero-stamp Passports Removed",
         x = "Regen Score",
         y = "Count") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tr", alpha = 0.8, width = 60) +
    theme(legend.position = "off")

ggsave(p103, filename = "outputs/non_sybil_score_regen.png", width = 12, height = 8)

p110 <- ggplot(data = binded_models %>% arrange(Logistic) %>%
           ungroup() %>%
           mutate(ID = 1:nrow(.)), aes(x = ID, y = Logistic)) +
    geom_point() +
    scale_x_continuous(breaks = scales::pretty_breaks(n = 20)) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 20),
                       labels = scales::percent,
                       limits = c(0, 1)) +
    labs(title = "Sorted Probability Scores for All Passports",
         subtitle = "For the Logistic Regression Model",
         y = "Predicted Probability (%)",
         x = "ID") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 80)

ggsave(p110, filename = "outputs/non_sybil_probability_logistic_allpassports.png", width = 12, height = 8)

p111 <- ggplot(data = binded_models %>% arrange(Regularized) %>%
           ungroup() %>%
           mutate(ID = 1:nrow(.)), aes(x = ID, y = Regularized)) +
    geom_point() +
    scale_x_continuous(breaks = scales::pretty_breaks(n = 20)) +
    scale_y_continuous(breaks = scales::pretty_breaks(n = 20),
                       labels = scales::percent,
                       limits = c(0, 1)) +
    labs(title = "Sorted Probability Scores for All Passports",
         subtitle = "For the Regularized Logistic Regression Model",
         y = "Predicted Probability (%)",
         x = "ID") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 80)

ggsave(p111, filename = "outputs/non_sybil_probability_regularized_allpassports.png", width = 12, height = 8)

p112 <- ggplot(data = binded_models %>% arrange(Kish) %>%
           ungroup() %>%
           mutate(ID = 1:nrow(.)), aes(x = ID, y = Kish)) +
    geom_point() +
    scale_x_continuous(breaks = scales::pretty_breaks(n = 20)) +
    scale_y_continuous(breaks = c(0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000),
                       trans=scales::pseudo_log_trans(base = 10),
                       limits = c(0, NA)) +
    labs(title = "Sorted USD($) Kish Scores for All Passports",
         subtitle = "Based on Kiashoraditya's Research",
         y = "Score ($)",
         x = "ID") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 60)

ggsave(p112, filename = "outputs/non_sybil_score_kish_allpassports.png", width = 12, height = 8)

p113 <- ggplot(data = binded_models %>% arrange(Regen) %>%
           ungroup() %>%
           mutate(ID = 1:nrow(.)), aes(x = ID, y = Regen)) +
    geom_point() +
    scale_x_continuous(breaks = scales::pretty_breaks(n = 20)) +
    scale_y_continuous(breaks = c(0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000),
                       trans=scales::pseudo_log_trans(base = 10),
                       limits = c(0, NA)) +
    labs(title = "Sorted Regen Scores for All Passports",
         y = "Score",
         x = "ID") +
    theme_grey() +
    watermark_img("images/gc.png", location = "tl", alpha = 0.8, width = 60)

ggsave(p113, filename = "outputs/non_sybil_score_regen_allpassports.png", width = 12, height = 8)

## Scatterplot Matrix
p200 <- ggpairs(binded_models %>% ungroup() %>% select(-handle, -class), title="correlogram with ggpairs()")

ggsave(p200, filename = "outputs/score_comparison.png", width = 12, height = 8)
