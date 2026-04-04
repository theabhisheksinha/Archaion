import { defineFunction } from "@aws-amplify/backend";
import { Duration, DockerImage } from "aws-cdk-lib";
import { Function, Runtime, Code } from "aws-cdk-lib/aws-lambda";
import * as path from "path";
import * as fs from "fs";
import { execSync } from "child_process";

const functionDir = __dirname;

export const modernizationHandler = defineFunction((scope) => {
  const fn = new Function(scope, "modernization-handler", {
    handler: "handler.handler",
    runtime: Runtime.PYTHON_3_11,
    timeout: Duration.seconds(20),
    code: Code.fromAsset(functionDir, {
      bundling: {
        image: DockerImage.fromRegistry("dummy"),
        local: {
          tryBundle(outputDir: string) {
            const req = path.join(functionDir, "requirements.txt");
            if (fs.existsSync(req)) {
              try {
                execSync(
                  `python3 -m pip install -r "${req}" -t "${outputDir}" --platform manylinux2014_x86_64 --only-binary=:all:`,
                  { stdio: "inherit" }
                );
              } catch {
                execSync(
                  `python -m pip install -r "${req}" -t "${outputDir}" --platform manylinux2014_x86_64 --only-binary=:all:`,
                  { stdio: "inherit" }
                );
              }
            }
            for (const entry of fs.readdirSync(functionDir)) {
              if (entry === ".git" || entry === "node_modules") continue;
              const src = path.join(functionDir, entry);
              const dest = path.join(outputDir, entry);
              fs.cpSync(src, dest, { recursive: true });
            }
            return true;
          },
        },
      },
    }),
  });
  return fn;
});
