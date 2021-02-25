/*
 * Copyright 2021 Rikai authors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package ai.eto.rikai.sql.spark.execution

import ai.eto.rikai.sql.model.ModelNotFoundException
import org.apache.spark.sql.{Row, SparkSession}

case class DropModelCommand(
    name: String
) extends ModelCommand {

  override def run(session: SparkSession): Seq[Row] = {
    if (!catalog(session).dropModel(name))
      throw new ModelNotFoundException(s"Model not found: ${name}")
    Seq.empty
  }
}
