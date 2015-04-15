import hudson.model.*

listAllJobsWithParams(Hudson.instance.items)

def listAllJobsWithParams(items) {
  for (item in items) {
    if (item.class.canonicalName != 'com.cloudbees.hudson.plugins.folder.Folder') {
       if (item.class.canonicalName) {
        prop = item.getProperty(ParametersDefinitionProperty.class)
        if(prop != null) {
          println("--- Start Parameters for " + count + ". " + item.name + " ---")
          for(param in prop.getParameterDefinitions()) {
            try {
              println(param.name + " " + param.defaultValue)
            }
            catch(Exception e) {
              println(param.name)
            }
          }
          println()
          println()
        }
      }
    } else {
        //print('[' + item.class.canonicalName + ']: ')
        //println(item.name)
        listAllJobsWithParams(((com.cloudbees.hudson.plugins.folder.Folder) item).getItems())
    }
  }
}
